import pytest

from tests.factories import GenreFactory, PublisherFactory, SystemFactory


@pytest.mark.parametrize("path", ["/systems/", "/systems/basic"])
async def test_no_empty_entry_when_there_is_no_custom_system(client, create, path):
    await create(SystemFactory, id="dnd5e")

    response = await client.get(path)

    assert [system["id"] for system in response.json()["systems"]] == ["dnd5e"]


class TestGetSystems:
    async def test_get_systems(self, client, create):
        publisher = await create(
            PublisherFactory, name="Wizards of the Coast", website="https://wizards.com"
        )
        genre = await create(GenreFactory, genre="Fantasy")
        await create(SystemFactory, id="custom")
        await create(
            SystemFactory,
            id="dnd5e",
            name="D&D 5e",
            sort_name="D&D 5e",
            publisher=publisher,
            genres=[genre],
            basics=[{"label": "Level", "url": "level"}],
            has_char_sheet=True,
            enabled=True,
        )

        response = await client.get("/systems/")

        systems = response.json()["systems"]
        dnd = next(system for system in systems if system["id"] == "dnd5e")
        assert dnd == {
            "id": "dnd5e",
            "name": "D&D 5e",
            "sort_name": "D&D 5e",
            "publisher": {
                "name": "Wizards of the Coast",
                "website": "https://wizards.com",
            },
            "genres": ["Fantasy"],
            "basics": [{"label": "Level", "url": "level"}],
            "has_char_sheet": True,
            "enabled": True,
        }

    async def test_get_systems_puts_custom_first_regardless_of_sort_name(
        self, client, create
    ):
        await create(SystemFactory, id="custom", sort_name="Zzz Custom")
        await create(SystemFactory, id="dnd5e", sort_name="D&D 5e")

        response = await client.get("/systems/")

        ids = [system["id"] for system in response.json()["systems"]]
        assert ids[0] == "custom"


class TestGetBasicSystems:
    async def test_get_basic_systems(self, client, create):
        genre = await create(GenreFactory, genre="Fantasy")
        await create(SystemFactory, id="custom")
        await create(
            SystemFactory,
            id="dnd5e",
            name="D&D 5e",
            sort_name="D&D 5e",
            genres=[genre],
            has_char_sheet=True,
        )

        response = await client.get("/systems/basic")

        systems = response.json()["systems"]
        dnd = next(system for system in systems if system["id"] == "dnd5e")
        assert dnd == {
            "id": "dnd5e",
            "name": "D&D 5e",
            "sort_name": "D&D 5e",
            "genres": ["Fantasy"],
            "has_char_sheet": True,
        }

    async def test_get_basic_systems_puts_custom_first_regardless_of_sort_name(
        self, client, create
    ):
        await create(SystemFactory, id="custom", sort_name="Zzz Custom")
        await create(SystemFactory, id="dnd5e", sort_name="D&D 5e")

        response = await client.get("/systems/basic")

        ids = [system["id"] for system in response.json()["systems"]]
        assert ids[0] == "custom"
