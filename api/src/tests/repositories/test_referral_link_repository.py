import pytest

from app.repositories.referral_link_repository import ReferralLinkRepository


class TestReferralLinkRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return ReferralLinkRepository(db_session)

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
