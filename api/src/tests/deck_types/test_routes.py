from tests.factories import DeckTypeFactory


class TestGetDeckTypes:
    async def test_get_deck_types_requires_auth(self, client):
        response = await client.get("/deck_types/")

        assert response.status_code == 403

    async def test_get_deck_types_empty_when_none_exist(self, authed_client):
        client, _user = authed_client

        response = await client.get("/deck_types/")

        assert response.status_code == 200
        assert response.json() == {"types": []}

    async def test_get_deck_types_returns_all_types(self, authed_client, create):
        client, _user = authed_client
        await create(DeckTypeFactory, short="tarot", name="Tarot Deck", deck_size=78)
        await create(DeckTypeFactory, short="pc", name="Playing Cards", deck_size=52)

        response = await client.get("/deck_types/")

        assert response.status_code == 200
        types = response.json()["types"]
        assert {t["short"] for t in types} == {"tarot", "pc"}
        tarot = next(t for t in types if t["short"] == "tarot")
        assert tarot == {"short": "tarot", "name": "Tarot Deck", "deck_size": 78}
