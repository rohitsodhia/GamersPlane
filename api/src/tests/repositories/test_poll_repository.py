import pytest
from sqlalchemy import func, select

from app.models import Poll, PollOption, PollVote
from app.repositories import PollRepository
from app.threads.poll_schemas import PollInput
from tests.factories import ForumFactory, ThreadFactory, UserFactory


def poll_input(*options, **overrides):
    """A ``PollInput`` of the given options (``(id, text)`` or just text)."""
    payload = {
        "question": "Best snack?",
        "options_per_user": 1,
        "allow_revoting": False,
        "options": [
            {"id": option[0], "text": option[1]}
            if isinstance(option, tuple)
            else {"text": option}
            for option in options
        ],
    }
    payload.update(overrides)
    return PollInput(**payload)


async def vote_count(db_session):
    return await db_session.scalar(select(func.count()).select_from(PollVote))


class TestPollRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return PollRepository(db_session, principal=None)

    @pytest.fixture
    async def thread(self, create, wrap_in_savepoint):
        forum = await create(ForumFactory, heritage=[])
        return await create(ThreadFactory, forum=forum)

    @pytest.fixture
    async def poll(self, repository, thread):
        return await repository.create(
            thread.id, poll_input("Apples", "Bananas", "Cherries")
        )

    async def test_apply_edit_updates_reorders_removes_and_adds_options(
        self, repository, create, thread, poll
    ):
        apples, bananas, cherries = await repository.get_options(thread.id)
        voter = await create(UserFactory)
        await repository.replace_votes(thread.id, voter.id, [apples.id, bananas.id])

        await repository.apply_edit(
            poll,
            [apples, bananas, cherries],
            poll_input(
                "Dates",
                (apples.id, "Apricots"),
                (cherries.id, "Cherries"),
                question="Best fruit?",
                options_per_user=2,
                allow_revoting=True,
            ),
        )

        options = await repository.get_options(thread.id)
        assert [(o.text, o.position) for o in options] == [
            ("Dates", 0),
            ("Apricots", 1),
            ("Cherries", 2),
        ]
        # Kept options keep their ids (and so their votes); the removed one is
        # gone and the added one is new.
        old_ids = {apples.id, bananas.id, cherries.id}
        assert options[1].id == apples.id
        assert options[2].id == cherries.id
        assert options[0].id not in old_ids
        assert (poll.question, poll.options_per_user, poll.allow_revoting) == (
            "Best fruit?",
            2,
            True,
        )
        # The removed option's vote went with it; the kept option's stayed.
        assert await repository.user_votes(thread.id, voter.id) == [apples.id]

    async def test_delete_removes_poll_options_and_votes(
        self, repository, create, db_session, thread, poll
    ):
        options = await repository.get_options(thread.id)
        voter = await create(UserFactory)
        await repository.replace_votes(thread.id, voter.id, [options[0].id])

        await repository.delete(poll)

        assert await vote_count(db_session) == 0
        assert await db_session.scalar(select(func.count()).select_from(Poll)) == 0
        assert (
            await db_session.scalar(select(func.count()).select_from(PollOption)) == 0
        )

    async def test_replace_votes_replaces_the_users_but_not_others(
        self, repository, create, thread, poll
    ):
        apples, bananas, cherries = await repository.get_options(thread.id)
        voter = await create(UserFactory)
        other = await create(UserFactory)
        await repository.replace_votes(thread.id, voter.id, [apples.id])
        await repository.replace_votes(thread.id, other.id, [apples.id])

        await repository.replace_votes(thread.id, voter.id, [bananas.id, cherries.id])

        assert await repository.user_votes(thread.id, voter.id) == sorted(
            [bananas.id, cherries.id]
        )
        assert await repository.user_votes(thread.id, other.id) == [apples.id]

    async def test_max_votes_per_user_counts_the_busiest_voter(
        self, repository, create, thread, poll
    ):
        apples, bananas, cherries = await repository.get_options(thread.id)
        busy = await create(UserFactory)
        light = await create(UserFactory)
        await repository.replace_votes(thread.id, busy.id, [apples.id, bananas.id])
        await repository.replace_votes(thread.id, light.id, [cherries.id])

        assert await repository.max_votes_per_user(thread.id) == 2
        assert (
            await repository.max_votes_per_user(
                thread.id, excluding_option_ids=[apples.id]
            )
            == 1
        )

    async def test_max_votes_per_user_is_zero_without_votes(
        self, repository, thread, poll
    ):
        assert await repository.max_votes_per_user(thread.id) == 0
