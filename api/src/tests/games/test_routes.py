import pytest
from sqlalchemy import text

from app.models import Game, Player
from tests.factories import ForumFactory, SystemFactory


def _payload(**overrides):
    fields = {
        "title": "My Campaign",
        "system_id": "dnd5e",
        "allowed_char_sheets": [],
        "post_frequency": "3/w",
        "num_players": 4,
        "chars_per_player": 1,
        "description": None,
        "char_gen_info": None,
        "public": True,
        "recruitment_thread_id": None,
        "advanced_options": None,
    }
    fields.update(overrides)
    return fields


class TestCreateGame:
    @pytest.fixture(autouse=True)
    async def games_root_forum(self, create, db_session):
        forum = await create(ForumFactory, id=2, heritage=[])
        # Forcing an explicit id bypasses the "forums_id_seq" sequence, so any
        # later auto-generated forum id in this test could collide with it.
        await db_session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('forums', 'id'), "
                "(SELECT MAX(id) FROM forums))"
            )
        )
        return forum

    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e")

    async def test_create_game_requires_auth(self, client, system):
        response = await client.post("/games/", json=_payload())

        assert response.status_code == 403

    async def test_create_game(self, authed_client, system):
        client, _user = authed_client

        response = await client.post("/games/", json=_payload())

        assert response.status_code == 200
        assert response.json()["id"] is not None

    async def test_create_game_makes_creator_a_gm_player(
        self, authed_client, system, db_session
    ):
        client, user = authed_client

        response = await client.post("/games/", json=_payload())

        game_id = response.json()["id"]
        player = await db_session.get(Player, {"game_id": game_id, "user_id": user.id})
        assert player is not None
        assert player.is_gm is True

    async def test_create_game_system_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/games/", json=_payload(system_id="does-not-exist")
        )

        assert response.status_code == 404

    async def test_create_game_allowed_char_sheet_not_found(
        self, authed_client, system
    ):
        client, _user = authed_client

        response = await client.post(
            "/games/",
            json=_payload(allowed_char_sheets=["does-not-exist"]),
        )

        assert response.status_code == 404

    async def test_create_game_with_allowed_char_sheets(
        self, authed_client, system, create
    ):
        client, _user = authed_client
        sheet = await create(SystemFactory, id="sheet-a")

        response = await client.post(
            "/games/",
            json=_payload(allowed_char_sheets=[sheet.id]),
        )

        assert response.status_code == 200

    async def test_create_game_strips_and_converts_title(
        self, authed_client, system, db_session
    ):
        client, _user = authed_client

        response = await client.post(
            "/games/", json=_payload(title="  Line one\nLine two  ")
        )

        assert response.status_code == 200
        game = await db_session.get(Game, response.json()["id"])
        assert game.title == "Line one<br>Line two"
