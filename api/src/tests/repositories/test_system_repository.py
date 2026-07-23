import pytest

from app.repositories.system_repository import SystemRepository
from tests.factories import GenreFactory, PublisherFactory


class TestSystemRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return SystemRepository(db_session)

    async def test_add(self, repository, create):
        publisher = await create(PublisherFactory)
        genre = await create(GenreFactory)

        system = await repository.add(
            id="dnd5e",
            name="D&D 5e",
            sort_name="D&D 5e",
            publisher_id=publisher.id,
            genres=[genre],
            basics=[{"label": "Level", "type": "number"}],
        )

        assert system.id == "dnd5e"
        assert system.name == "D&D 5e"
        assert system.sort_name == "D&D 5e"
        assert system.publisher_id == publisher.id
        assert system.genres == [genre]
        assert system.basics == [{"label": "Level", "type": "number"}]
        assert system.has_char_sheet is False
        assert system.enabled is True

    async def test_get(self, repository, create):
        publisher = await create(PublisherFactory)
        genre = await create(GenreFactory)
        await repository.add(
            id="dnd5e",
            name="D&D 5e",
            sort_name="D&D 5e",
            publisher_id=publisher.id,
            genres=[genre],
            basics=[],
        )

        systems = (await repository.get()).all()

        assert len(systems) == 1
        assert systems[0].id == "dnd5e"
        assert systems[0].publisher.id == publisher.id
        assert systems[0].genres == [genre]

    async def test_get_empty(self, repository):
        systems = (await repository.get()).all()

        assert systems == []
