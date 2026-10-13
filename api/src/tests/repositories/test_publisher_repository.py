import pytest

from app.repositories.publisher_repository import PublisherRepository


class TestPublisherRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return PublisherRepository(db_session)

    async def test_add_and_get_all(self, repository):
        added = await repository.add("Wizards of the Coast", "https://wizards.com")
        await repository.add("Paizo", None)

        publishers = await repository.get_all()

        assert added.id is not None
        assert added.name == "Wizards of the Coast"
        assert added.website == "https://wizards.com"
        assert {publisher.name for publisher in publishers} == {
            "Wizards of the Coast",
            "Paizo",
        }
