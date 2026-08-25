import pytest
from sqlalchemy import text
from sqlalchemy.orm import selectinload

from app.models import FavoriteGame, Game, Player
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
        assert body["players"] == []
        assert body["viewer_state"] is None
        assert body["favorited"] is False

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
        invited = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(game.id, applied.id)
        await player_repository.attach_player_to_game(
            game.id, accepted.id, state=Player.States.ACCEPTED
        )
        await player_repository.attach_player_to_game(
            game.id, invited.id, state=Player.States.INVITED
        )

        client = self._auth_as(client, gm)
        response = await client.get(f"/games/{game.id}")

        player_user_ids = {p["id"] for p in response.json()["players"]}
        assert player_user_ids == {applied.id, accepted.id, invited.id}

    async def test_get_game_as_non_gm_only_returns_accepted_players(
        self, authed_client, db_session, gm, game, create
    ):
        client, _user = authed_client
        player_repository = PlayerRepository(db_session, principal=gm)
        applied = await create(ActivatedUserFactory)
        accepted = await create(ActivatedUserFactory)
        invited = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(game.id, applied.id)
        await player_repository.attach_player_to_game(
            game.id, accepted.id, state=Player.States.ACCEPTED
        )
        await player_repository.attach_player_to_game(
            game.id, invited.id, state=Player.States.INVITED
        )

        response = await client.get(f"/games/{game.id}")

        player_user_ids = {p["id"] for p in response.json()["players"]}
        assert player_user_ids == {accepted.id}

    async def test_get_game_anonymous_only_returns_accepted_players(
        self, client, db_session, gm, game, create
    ):
        player_repository = PlayerRepository(db_session, principal=gm)
        applied = await create(ActivatedUserFactory)
        accepted = await create(ActivatedUserFactory)
        invited = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(game.id, applied.id)
        await player_repository.attach_player_to_game(
            game.id, accepted.id, state=Player.States.ACCEPTED
        )
        await player_repository.attach_player_to_game(
            game.id, invited.id, state=Player.States.INVITED
        )

        response = await client.get(f"/games/{game.id}")

        player_user_ids = {p["id"] for p in response.json()["players"]}
        assert player_user_ids == {accepted.id}

    async def test_get_game_viewer_state_reflects_own_invite(
        self, client, db_session, gm, game, create
    ):
        player_repository = PlayerRepository(db_session, principal=gm)
        invitee = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(
            game.id, invitee.id, state=Player.States.INVITED
        )

        client = self._auth_as(client, invitee)
        response = await client.get(f"/games/{game.id}")

        body = response.json()
        assert body["viewer_state"] == "invited"
        # The invited player isn't accepted, so they still don't show up in
        # the public players list even though they can see their own state.
        assert body["players"] == []

    async def test_get_game_viewer_state_none_when_not_a_player(
        self, client, db_session, gm, game, create
    ):
        other_user = await create(ActivatedUserFactory)

        client = self._auth_as(client, other_user)
        response = await client.get(f"/games/{game.id}")

        assert response.json()["viewer_state"] is None

    async def test_get_game_player_fields(self, client, db_session, gm, game, create):
        player_repository = PlayerRepository(db_session, principal=gm)
        user = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(
            game.id, user.id, is_gm=False, state=Player.States.ACCEPTED
        )

        response = await client.get(f"/games/{game.id}")

        players = response.json()["players"]
        assert players == [
            {
                "id": user.id,
                "username": user.username,
                "is_gm": False,
                "state": "accepted",
            }
        ]

    async def test_get_game_favorited_true_when_favorited(self, authed_client, game):
        client, _user = authed_client
        await client.post(f"/games/{game.id}/favorite")

        response = await client.get(f"/games/{game.id}")

        assert response.json()["favorited"] is True


class TestUpdateGame:
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
            None,
            None,
            True,
            None,
            None,
        )

    def _auth_as(self, client, user):
        token = user.generate_jwt()
        client.headers["Authorization"] = f"Bearer {token}"
        return client

    async def test_update_game_requires_auth(self, client, game):
        response = await client.patch(f"/games/{game.id}", json=_payload())

        assert response.status_code == 403

    async def test_update_game_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.patch("/games/999999", json=_payload())

        assert response.status_code == 404

    async def test_update_game_not_gm_forbidden(self, authed_client, game):
        client, _user = authed_client

        response = await client.patch(f"/games/{game.id}", json=_payload())

        assert response.status_code == 403

    async def test_update_game_as_gm_updates_fields(self, client, db_session, game, gm):
        client = self._auth_as(client, gm)

        response = await client.patch(
            f"/games/{game.id}",
            json=_payload(
                title="New Title",
                post_frequency="1/d",
                num_players=6,
                chars_per_player=2,
                description={"summary": "updated"},
                char_gen_info={"info": "updated"},
                public=False,
                recruitment_thread_id=42,
                advanced_options={"foo": "bar"},
            ),
        )

        assert response.status_code == 200
        assert response.json()["id"] == game.id
        updated = await db_session.get(Game, game.id)
        assert updated.title == "New Title"
        assert updated.post_frequency.times_per == 1
        assert updated.post_frequency.per_period == "d"
        assert updated.num_players == 6
        assert updated.chars_per_player == 2
        assert updated.description == {"summary": "updated"}
        assert updated.char_gen_info == {"info": "updated"}
        assert updated.public is False
        assert updated.recruitment_thread_id == 42
        assert updated.advanced_options == {"foo": "bar"}

    async def test_update_game_strips_and_converts_title(
        self, client, db_session, game, gm
    ):
        client = self._auth_as(client, gm)

        response = await client.patch(
            f"/games/{game.id}", json=_payload(title="  Line one\nLine two  ")
        )

        assert response.status_code == 200
        updated = await db_session.get(Game, game.id)
        assert updated.title == "Line one<br>Line two"

    async def test_update_game_soft_deleted_not_found(
        self, client, db_session, game, gm
    ):
        client = self._auth_as(client, gm)
        game.deleted = game.created
        db_session.add(game)
        await db_session.flush()

        response = await client.patch(f"/games/{game.id}", json=_payload())

        assert response.status_code == 404

    async def test_update_game_allowed_char_sheets(
        self, client, db_session, game, gm, create
    ):
        client = self._auth_as(client, gm)
        sheet = await create(SystemFactory, id="sheet-a")

        response = await client.patch(
            f"/games/{game.id}",
            json=_payload(allowed_char_sheets=[sheet.id]),
        )

        assert response.status_code == 200
        updated = await db_session.get(
            Game, game.id, options=[selectinload(Game.allowed_char_sheets)]
        )
        assert [s.id for s in updated.allowed_char_sheets] == [sheet.id]

    async def test_update_game_system_not_found(self, client, game, gm):
        client = self._auth_as(client, gm)

        response = await client.patch(
            f"/games/{game.id}", json=_payload(system_id="does-not-exist")
        )

        assert response.status_code == 404

    async def test_update_game_allowed_char_sheet_not_found(self, client, game, gm):
        client = self._auth_as(client, gm)

        response = await client.patch(
            f"/games/{game.id}",
            json=_payload(allowed_char_sheets=["does-not-exist"]),
        )

        assert response.status_code == 404


class TestFavoriteGame:
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
            None,
            None,
            True,
            None,
            None,
        )

    async def test_favorite_game_requires_auth(self, client, game):
        response = await client.post(f"/games/{game.id}/favorite")

        assert response.status_code == 403

    async def test_favorite_game_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.post("/games/999999/favorite")

        assert response.status_code == 404

    async def test_favorite_game_adds_favorite(self, authed_client, game, db_session):
        client, user = authed_client

        response = await client.post(f"/games/{game.id}/favorite")

        assert response.status_code == 200
        assert response.json() == {"favorite": True}
        favorite = await db_session.get(FavoriteGame, (user.id, game.id))
        assert favorite is not None

    async def test_favorite_game_twice_removes_favorite(
        self, authed_client, game, db_session
    ):
        client, user = authed_client
        await client.post(f"/games/{game.id}/favorite")

        response = await client.post(f"/games/{game.id}/favorite")

        assert response.status_code == 200
        assert response.json() == {"favorite": False}
        favorite = await db_session.get(FavoriteGame, (user.id, game.id))
        assert favorite is None

    async def test_favorite_game_soft_deleted_not_found(
        self, authed_client, game, db_session
    ):
        client, _user = authed_client
        game.deleted = game.created
        db_session.add(game)
        await db_session.flush()

        response = await client.post(f"/games/{game.id}/favorite")

        assert response.status_code == 404


class TestInvitePlayer:
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
        game = await game_repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "3/w",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )
        # Real games always have their GM attached as a player (see
        # create_game in routes.py); invite_player's GM check reads this
        # Player row, not Game.gm_id, so the fixture must mirror that.
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, gm.id, is_gm=True, state=Player.States.ACCEPTED
        )
        return game

    def _auth_as(self, client, user):
        token = user.generate_jwt()
        client.headers["Authorization"] = f"Bearer {token}"
        return client

    async def test_invite_player_requires_auth(self, client, game):
        response = await client.post(
            f"/games/{game.id}/invite", json={"username": "someone"}
        )

        assert response.status_code == 403

    async def test_invite_player_game_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/games/999999/invite", json={"username": "someone"}
        )

        assert response.status_code == 404

    async def test_invite_player_not_gm_forbidden(self, authed_client, game):
        client, _user = authed_client

        response = await client.post(
            f"/games/{game.id}/invite", json={"username": "someone"}
        )

        assert response.status_code == 403

    async def test_invite_player_user_not_found(self, client, game, gm):
        client = self._auth_as(client, gm)

        response = await client.post(
            f"/games/{game.id}/invite", json={"username": "does-not-exist"}
        )

        assert response.status_code == 404

    async def test_invite_player_creates_invited_player(
        self, client, db_session, game, gm, create
    ):
        client = self._auth_as(client, gm)
        invitee = await create(ActivatedUserFactory)

        response = await client.post(
            f"/games/{game.id}/invite", json={"username": invitee.username}
        )

        assert response.status_code == 204
        player = await db_session.get(
            Player, {"game_id": game.id, "user_id": invitee.id}
        )
        assert player is not None
        assert player.state == Player.States.INVITED
        assert player.is_gm is False

    async def test_invite_player_already_invited_conflict(
        self, client, db_session, game, gm, create
    ):
        client = self._auth_as(client, gm)
        invitee = await create(ActivatedUserFactory)
        await client.post(
            f"/games/{game.id}/invite", json={"username": invitee.username}
        )

        response = await client.post(
            f"/games/{game.id}/invite", json={"username": invitee.username}
        )

        assert response.status_code == 409
        # The test client's db_session override bypasses the commit/rollback
        # that DBSessionDependency normally does at the request boundary, so
        # the failed flush's rolled-back transaction state must be cleared
        # manually or it poisons every later test sharing this session.
        await db_session.rollback()


class TestApplyToGame:
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
        game = await game_repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "3/w",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, gm.id, is_gm=True, state=Player.States.ACCEPTED
        )
        return game

    def _auth_as(self, client, user):
        token = user.generate_jwt()
        client.headers["Authorization"] = f"Bearer {token}"
        return client

    async def test_apply_to_game_requires_auth(self, client, game):
        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 403

    async def test_apply_to_game_game_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.post("/games/999999/apply")

        assert response.status_code == 404

    async def test_apply_to_game_closed_forbidden(
        self, client, db_session, game, gm, create
    ):
        game_repository = GameRepository(db_session, principal=gm)
        await game_repository.update(game, status=Game.Statuses.CLOSED)
        applicant = await create(ActivatedUserFactory)
        client = self._auth_as(client, applicant)

        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 403

    async def test_apply_to_game_not_public_forbidden(
        self, client, db_session, game, gm, create
    ):
        game_repository = GameRepository(db_session, principal=gm)
        await game_repository.update(game, public=False)
        applicant = await create(ActivatedUserFactory)
        client = self._auth_as(client, applicant)

        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 403

    async def test_apply_to_game_creates_applied_player(
        self, client, db_session, game, create
    ):
        applicant = await create(ActivatedUserFactory)
        client = self._auth_as(client, applicant)

        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 204
        player = await db_session.get(
            Player, {"game_id": game.id, "user_id": applicant.id}
        )
        assert player is not None
        assert player.state == Player.States.APPLIED
        assert player.is_gm is False

    async def test_apply_to_game_already_player_conflict(
        self, client, db_session, game, gm
    ):
        client = self._auth_as(client, gm)

        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 409
        # The test client's db_session override bypasses the commit/rollback
        # that DBSessionDependency normally does at the request boundary, so
        # the failed flush's rolled-back transaction state must be cleared
        # manually or it poisons every later test sharing this session.
        await db_session.rollback()

    async def test_apply_to_game_apply_twice_conflict(
        self, client, db_session, game, create
    ):
        applicant = await create(ActivatedUserFactory)
        client = self._auth_as(client, applicant)
        await client.post(f"/games/{game.id}/apply")

        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 409
        # The test client's db_session override bypasses the commit/rollback
        # that DBSessionDependency normally does at the request boundary, so
        # the failed flush's rolled-back transaction state must be cleared
        # manually or it poisons every later test sharing this session.
        await db_session.rollback()


class TestToggleGameFlag:
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
            None,
            None,
            True,
            None,
            None,
        )

    async def test_toggle_game_flag_requires_auth(self, client, game):
        response = await client.patch(f"/games/{game.id}/toggle/public")

        assert response.status_code == 403

    async def test_toggle_game_flag_game_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.patch("/games/999999/toggle/public")

        assert response.status_code == 404

    async def test_toggle_game_flag_invalid_key_not_found(self, authed_client, game):
        client, _user = authed_client

        response = await client.patch(f"/games/{game.id}/toggle/not-a-real-key")

        assert response.status_code == 422

    async def test_toggle_public_flips_the_flag(self, authed_client, game, db_session):
        client, _user = authed_client
        assert game.public is True

        response = await client.patch(f"/games/{game.id}/toggle/public")

        assert response.status_code == 204
        game = await db_session.get(Game, game.id)
        assert game.public is False

    async def test_toggle_public_twice_flips_back(self, authed_client, game, db_session):
        client, _user = authed_client
        await client.patch(f"/games/{game.id}/toggle/public")

        response = await client.patch(f"/games/{game.id}/toggle/public")

        assert response.status_code == 204
        game = await db_session.get(Game, game.id)
        assert game.public is True

    async def test_toggle_status_flips_the_flag(self, authed_client, game, db_session):
        client, _user = authed_client
        assert game.status == Game.Statuses.OPEN

        response = await client.patch(f"/games/{game.id}/toggle/status")

        assert response.status_code == 204
        game = await db_session.get(Game, game.id)
        assert game.status == Game.Statuses.CLOSED

    async def test_toggle_status_twice_flips_back(self, authed_client, game, db_session):
        client, _user = authed_client
        await client.patch(f"/games/{game.id}/toggle/status")

        response = await client.patch(f"/games/{game.id}/toggle/status")

        assert response.status_code == 204
        game = await db_session.get(Game, game.id)
        assert game.status == Game.Statuses.OPEN


class TestDeletePlayer:
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
        game = await game_repository.create(
            "My Campaign",
            system.id,
            [],
            gm.id,
            "3/w",
            4,
            1,
            None,
            None,
            True,
            None,
            None,
        )
        # Real games always have their GM attached as a player (see
        # create_game in routes.py); delete_player's GM check reads this
        # Player row, not Game.gm_id, so the fixture must mirror that.
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, gm.id, is_gm=True, state=Player.States.ACCEPTED
        )
        return game

    @pytest.fixture
    async def invitee(self, db_session, gm, game, create):
        invitee = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, invitee.id, state=Player.States.INVITED
        )
        return invitee

    def _auth_as(self, client, user):
        token = user.generate_jwt()
        client.headers["Authorization"] = f"Bearer {token}"
        return client

    async def test_delete_player_requires_auth(self, client, game, invitee):
        response = await client.delete(f"/games/{game.id}/player/{invitee.id}")

        assert response.status_code == 403

    async def test_delete_player_game_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.delete("/games/999999/player/1")

        assert response.status_code == 404

    async def test_delete_player_not_gm_and_not_self_forbidden(
        self, authed_client, game, invitee
    ):
        client, _user = authed_client

        response = await client.delete(f"/games/{game.id}/player/{invitee.id}")

        assert response.status_code == 403

    @pytest.mark.parametrize(
        "state", [Player.States.INVITED, Player.States.ACCEPTED]
    )
    async def test_delete_player_as_gm_removes_player(
        self, client, db_session, game, gm, create, state
    ):
        target = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(game.id, target.id, state=state)
        client = self._auth_as(client, gm)

        response = await client.delete(f"/games/{game.id}/player/{target.id}")

        assert response.status_code == 204
        player = await db_session.get(Player, {"game_id": game.id, "user_id": target.id})
        assert player is None

    @pytest.mark.parametrize(
        "state", [Player.States.INVITED, Player.States.ACCEPTED]
    )
    async def test_delete_player_as_self_removes_own_player(
        self, client, db_session, game, gm, create, state
    ):
        target = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(game.id, target.id, state=state)
        client = self._auth_as(client, target)

        response = await client.delete(f"/games/{game.id}/player/{target.id}")

        assert response.status_code == 204
        player = await db_session.get(Player, {"game_id": game.id, "user_id": target.id})
        assert player is None

    async def test_delete_player_not_in_game_not_found(self, client, game, gm, create):
        client = self._auth_as(client, gm)
        stranger = await create(ActivatedUserFactory)

        response = await client.delete(f"/games/{game.id}/player/{stranger.id}")

        assert response.status_code == 404

    async def test_delete_player_primary_gm_forbidden(self, client, game, gm):
        client = self._auth_as(client, gm)

        response = await client.delete(f"/games/{game.id}/player/{gm.id}")

        assert response.status_code == 403
