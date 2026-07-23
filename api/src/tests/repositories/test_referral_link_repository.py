import pytest
from sqlalchemy import select

from app.models import ReferralLink
from app.repositories.referral_link_repository import ReferralLinkRepository


class TestReferralLinkRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return ReferralLinkRepository(db_session)

    async def test_add(self, repository):
        await repository.add("Amazon", "https://amazon.com", 1)

        links = await repository.get_all()

        assert len(links) == 1
        assert links[0].title == "Amazon"
        assert links[0].link == "https://amazon.com"
        assert links[0].order == 1
        assert links[0].enabled is True

    async def test_add_disabled(self, repository, db_session):
        await repository.add("Amazon", "https://amazon.com", 1, enabled=False)

        links = (await db_session.scalars(select(ReferralLink))).all()

        assert links[0].enabled is False

    async def test_get_all_orders_by_order(self, repository):
        await repository.add("Third", "https://third.com", 3)
        await repository.add("First", "https://first.com", 1)
        await repository.add("Second", "https://second.com", 2)

        links = await repository.get_all()

        assert [link.title for link in links] == ["First", "Second", "Third"]

    async def test_get_all_excludes_disabled(self, repository):
        await repository.add("Enabled", "https://enabled.com", 1, enabled=True)
        await repository.add("Disabled", "https://disabled.com", 2, enabled=False)

        links = await repository.get_all()

        assert [link.title for link in links] == ["Enabled"]

    async def test_get_all_empty(self, repository):
        links = await repository.get_all()

        assert links == []
