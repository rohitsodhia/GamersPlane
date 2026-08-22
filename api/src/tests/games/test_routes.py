import pytest
from sqlalchemy import text

from app.models import Game, Player
from app.repositories import GameRepository, PlayerRepository
from tests.factories import ActivatedUserFactory, ForumFactory, SystemFactory


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


class TestGetGame:
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

    @pytest.fixture
    async def gm(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def game(self, db_session, gm, system):
        game_repository = GameRepository(db_session, principal=gm)
        return await game_repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "3/w",
            4,
            1,
            {"summary": "A tale"},
            {"info": "roll for stats"},
            True,
            None,
            None,
        )

    def _auth_as(self, client, user):
        token = user.generate_jwt()
        client.headers["Authorization"] = f"Bearer {token}"
        return client

    async def test_get_game_not_found(self, client):
        response = await client.get("/games/999999")

        assert response.status_code == 404

    async def test_get_game_is_public(self, client, game):
        response = await client.get(f"/games/{game.id}")

        assert response.status_code == 200

    async def test_get_game_returns_fields(self, client, game, system, gm):
        response = await client.get(f"/games/{game.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == game.id
        assert body["title"] == "My Campaign"
        assert body["system"] == system.id
        assert body["allowed_char_sheets"] == []
        assert body["gm"] == {"id": gm.id, "username": gm.username}
        assert body["created"] is not None
        assert body["end"] is None
        assert body["post_frequency"] == {"times_per": 3, "per_period": "w"}
        assert body["num_players"] == 4
        assert body["chars_per_player"] == 1
        assert body["description"] == {"summary": "A tale"}
        assert body["char_gen_info"] == {"info": "roll for stats"}
        assert body["root_forum_id"] == game.root_forum_id
        assert body["status"] == "open"
        assert body["public"] is True
        assert body["recruitment_thread_id"] is None
        assert body["advanced_options"] is None
        assert body["retired"] is None
        assert body["players"] == {"players": []}

    async def test_get_game_allowed_char_sheets_returns_ids(
        self, client, db_session, gm, system, create
    ):
        sheet = await create(SystemFactory, id="sheet-a")
        game_repository = GameRepository(db_session, principal=gm)
        game = await game_repository.create(
            "My Campaign",
            system.id,
            [sheet.id],
            gm.id,
            "1/d",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )

        response = await client.get(f"/games/{game.id}")

        assert response.json()["allowed_char_sheets"] == [sheet.id]

    async def test_get_game_status_closed(self, client, db_session, game):
        game.status = Game.Statuses.CLOSED
        db_session.add(game)
        await db_session.flush()

        response = await client.get(f"/games/{game.id}")

        assert response.json()["status"] == "closed"

    async def test_get_game_as_gm_returns_players_in_all_states(
        self, client, db_session, gm, game, create
    ):
        player_repository = PlayerRepository(db_session, principal=gm)
        applied = await create(ActivatedUserFactory)
        accepted = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(game.id, applied.id)
        await player_repository.attach_player_to_game(
            game.id, accepted.id, state=Player.States.ACCEPTED
        )

        client = self._auth_as(client, gm)
        response = await client.get(f"/games/{game.id}")

        player_user_ids = {p["id"] for p in response.json()["players"]["players"]}
        assert player_user_ids == {applied.id, accepted.id}

    async def test_get_game_as_non_gm_only_returns_accepted_players(
        self, authed_client, db_session, gm, game, create
    ):
        client, _user = authed_client
        player_repository = PlayerRepository(db_session, principal=gm)
        applied = await create(ActivatedUserFactory)
        accepted = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(game.id, applied.id)
        await player_repository.attach_player_to_game(
            game.id, accepted.id, state=Player.States.ACCEPTED
        )

        response = await client.get(f"/games/{game.id}")

        player_user_ids = {p["id"] for p in response.json()["players"]["players"]}
        assert player_user_ids == {accepted.id}

    async def test_get_game_anonymous_only_returns_accepted_players(
        self, client, db_session, gm, game, create
    ):
        player_repository = PlayerRepository(db_session, principal=gm)
        applied = await create(ActivatedUserFactory)
        accepted = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(game.id, applied.id)
        await player_repository.attach_player_to_game(
            game.id, accepted.id, state=Player.States.ACCEPTED
        )

        response = await client.get(f"/games/{game.id}")

        player_user_ids = {p["id"] for p in response.json()["players"]["players"]}
        assert player_user_ids == {accepted.id}

    async def test_get_game_player_fields(self, client, db_session, gm, game, create):
        player_repository = PlayerRepository(db_session, principal=gm)
        user = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(
            game.id, user.id, is_gm=False, state=Player.States.ACCEPTED
        )

        response = await client.get(f"/games/{game.id}")

        players = response.json()["players"]["players"]
        assert players == [
            {
                "id": user.id,
                "username": user.username,
                "is_gm": False,
                "state": "accepted",
            }
        ]
