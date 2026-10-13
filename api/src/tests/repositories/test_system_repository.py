import pytest

from app.repositories.system_repository import SystemRepository
from tests.factories import GenreFactory, PublisherFactory


class TestSystemRepository:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return SystemRepository(db_session)

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

    @pytest.mark.parametrize(
        ("kwargs", "expected_ids"),
        [
            pytest.param({}, ["enabled-system"], id="excludes_disabled_by_default"),
            pytest.param(
                {"only_enabled": False},
                ["disabled-system", "enabled-system"],
                id="includes_disabled_when_only_enabled_false",
            ),
        ],
    )
    async def test_get_only_enabled_filter(
        self, repository, create, kwargs, expected_ids
    ):
        publisher = await create(PublisherFactory)
        await repository.add(
            id="enabled-system",
            name="Enabled",
            sort_name="Enabled",
            publisher_id=publisher.id,
            genres=[],
            basics=[],
            enabled=True,
        )
        await repository.add(
            id="disabled-system",
            name="Disabled",
            sort_name="Disabled",
            publisher_id=publisher.id,
            genres=[],
            basics=[],
            enabled=False,
        )

        systems = (await repository.get(**kwargs)).all()

        assert sorted(system.id for system in systems) == expected_ids
