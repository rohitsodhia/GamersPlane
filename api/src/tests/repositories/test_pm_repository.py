import pytest

from app.exceptions import NotFoundException
from app.repositories.pm_repository import (
    NoRecipientException,
    PMRepository,
    PMSelfException,
)
from tests.factories import PMFactory, UserFactory


class TestPMRepository:
    @pytest.fixture
    async def alice(self, create, wrap_in_savepoint):
        return await create(UserFactory, username="alice")

    @pytest.fixture
    async def bob(self, create, wrap_in_savepoint):
        return await create(UserFactory, username="bob")

    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint, alice):
        return PMRepository(db_session, principal=alice)

    async def test_get_pms_inbox(self, repository, create, alice, bob):
        await create(PMFactory, recipient=alice, sender=bob, title="Hi")

        pms = await repository.get_pms(user_id=alice.id, box="inbox")

        pms = list(pms)
        assert len(pms) == 1
        assert pms[0].title == "Hi"

    async def test_get_pms_outbox(self, repository, create, alice, bob):
        await create(PMFactory, recipient=bob, sender=alice, title="Sent")
        await create(PMFactory, recipient=alice, sender=bob, title="Received")

        pms = list(await repository.get_pms(user_id=alice.id, box="outbox"))

        assert len(pms) == 1
        assert pms[0].title == "Sent"

    async def test_get_pms_excludes_recipient_deleted(
        self, repository, create, alice, bob
    ):
        from datetime import datetime, timezone

        await create(
            PMFactory,
            recipient=alice,
            sender=bob,
            recipient_deleted=datetime.now(timezone.utc),
        )

        pms = list(await repository.get_pms(user_id=alice.id, box="inbox"))

        assert pms == []

    async def test_get_pms_excludes_sender_deleted(
        self, repository, create, alice, bob
    ):
        from datetime import datetime, timezone

        await create(
            PMFactory,
            recipient=bob,
            sender=alice,
            sender_deleted=datetime.now(timezone.utc),
        )

        pms = list(await repository.get_pms(user_id=alice.id, box="outbox"))

        assert pms == []

    async def test_get_pms_orders_by_datestamp_desc(
        self, repository, create, alice, bob
    ):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        await create(
            PMFactory, recipient=alice, sender=bob, title="Older", datestamp=now
        )
        await create(
            PMFactory,
            recipient=alice,
            sender=bob,
            title="Newer",
            datestamp=now + timedelta(minutes=1),
        )

        pms = list(await repository.get_pms(user_id=alice.id, box="inbox"))

        assert [pm.title for pm in pms] == ["Newer", "Older"]

    async def test_get_pms_respects_pagination(self, repository, create, alice, bob):
        for i in range(3):
            await create(PMFactory, recipient=alice, sender=bob, title=f"PM {i}")

        pms = list(
            await repository.get_pms(user_id=alice.id, box="inbox", page=1, limit=2)
        )

        assert len(pms) == 2

    async def test_count_pms(self, repository, create, alice, bob):
        await create(PMFactory, recipient=alice, sender=bob)
        await create(PMFactory, recipient=alice, sender=bob)

        count = await repository.count_pms(user_id=alice.id, box="inbox")

        assert count == 2

    async def test_get_pm_as_recipient(self, repository, create, alice, bob):
        pm = await create(PMFactory, recipient=alice, sender=bob)

        found = await repository.get_pm(pm.id)

        assert found.id == pm.id

    async def test_get_pm_as_sender(self, create, alice, bob, db_session):
        pm = await create(PMFactory, recipient=bob, sender=alice)
        repository = PMRepository(db_session, principal=alice)

        found = await repository.get_pm(pm.id)

        assert found.id == pm.id

    async def test_get_pm_not_found(self, repository):
        with pytest.raises(NotFoundException):
            await repository.get_pm(999999)

    async def test_get_pm_not_found_for_uninvolved_user(self, create, bob, db_session):
        other = await create(UserFactory, username="charlie")
        third = await create(UserFactory, username="dave")
        pm = await create(PMFactory, recipient=bob, sender=other)
        repository = PMRepository(db_session, principal=third)

        with pytest.raises(NotFoundException):
            await repository.get_pm(pm.id)

    async def test_get_pm_history(self, repository, create, alice, bob):
        original = await create(PMFactory, recipient=alice, sender=bob)
        reply = await create(
            PMFactory,
            recipient=bob,
            sender=alice,
            history_ids=[original.id],
        )

        history = await repository.get_pm_history(reply)

        assert [pm.id for pm in history] == [original.id]

    async def test_get_pm_history_excludes_pms_not_involving_user(
        self, repository, create, alice, bob
    ):
        other = await create(UserFactory, username="charlie")
        unrelated = await create(PMFactory, recipient=other, sender=bob)
        reply = await create(
            PMFactory,
            recipient=bob,
            sender=alice,
            history_ids=[unrelated.id],
        )

        history = await repository.get_pm_history(reply)

        assert history == []

    async def test_send_pm(self, repository, bob):
        pm = await repository.send_pm(
            recipient_username=bob.username, title="Hello", message="Hi there"
        )

        assert pm.title == "Hello"
        assert pm.message == "Hi there"
        assert pm.recipient_id == bob.id
        assert pm.sender_id == repository.principal.id

    async def test_send_pm_no_recipient(self, repository):
        with pytest.raises(NoRecipientException):
            await repository.send_pm(
                recipient_username="nobody", title="Hello", message="Hi there"
            )

    async def test_send_pm_to_self(self, repository, alice):
        with pytest.raises(PMSelfException):
            await repository.send_pm(
                recipient_username=alice.username, title="Hello", message="Hi there"
            )

    async def test_send_pm_with_reply_to_sets_history(self, repository, create, bob):
        original = await create(PMFactory, recipient=repository.principal, sender=bob)

        pm = await repository.send_pm(
            recipient_username=bob.username,
            title="Re: Hello",
            message="Reply",
            reply_to_id=original.id,
        )

        assert pm.reply_to_id == original.id
        assert pm.history_ids == [original.id]

    async def test_send_pm_with_invalid_reply_to_ignores_it(self, repository, bob):
        pm = await repository.send_pm(
            recipient_username=bob.username,
            title="Hello",
            message="Hi there",
            reply_to_id=999999,
        )

        assert pm.reply_to_id is None
        assert pm.history_ids == []

    async def test_delete_pm_as_recipient(self, repository, create, alice, bob):
        pm = await create(PMFactory, recipient=alice, sender=bob)

        await repository.delete_pm(pm.id)

        assert pm.recipient_deleted is not None
        assert pm.sender_deleted is None

    async def test_delete_pm_as_sender(self, create, alice, bob, db_session):
        pm = await create(PMFactory, recipient=bob, sender=alice)
        repository = PMRepository(db_session, principal=alice)

        await repository.delete_pm(pm.id)

        assert pm.sender_deleted is not None
        assert pm.recipient_deleted is None

    async def test_delete_pm_not_found(self, repository):
        with pytest.raises(NotFoundException):
            await repository.delete_pm(999999)
