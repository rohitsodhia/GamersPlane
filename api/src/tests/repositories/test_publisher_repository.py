import pytest

from app.repositories.publisher_repository import PublisherRepository


class TestPublisherRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return PublisherRepository(db_session)

    async def test_add(self, repository):
        publisher = await repository.add("Wizards of the Coast", "https://wizards.com")

        assert publisher.id is not None
        assert publisher.name == "Wizards of the Coast"
        assert publisher.website == "https://wizards.com"

    async def test_add_without_website(self, repository):
        publisher = await repository.add("Wizards of the Coast", None)

        assert publisher.id is not None
        assert publisher.website is None

    async def test_get_all(self, repository):
        await repository.add("Wizards of the Coast", "https://wizards.com")
        await repository.add("Paizo", None)

        publishers = await repository.get_all()

        assert {publisher.name for publisher in publishers} == {
            "Wizards of the Coast",
            "Paizo",
        }

    async def test_get_all_empty(self, repository):
        publishers = await repository.get_all()

        assert publishers == []
