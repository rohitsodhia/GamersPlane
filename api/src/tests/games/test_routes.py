from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.configs import configs
from app.models import (
    Deck,
    DeckPermission,
    FavoriteGame,
    Forum,
    Game,
    Player,
    RolePermission,
)
from app.repositories import (
    CharacterRepository,
    CharacterSheetRepository,
    DeckRepository,
    GameRepository,
    PlayerRepository,
    ReadTrackingRepository,
)
from tests.threads.test_search_routes import add_thread
from tests.factories import (
    ActivatedUserFactory,
    DeckTypeFactory,
    ForumFactory,
    RoleFactory,
    SystemFactory,
    ThreadFactory,
)

Verbs = RolePermission.ValidPermissions

SHEET_LAYOUT = {
    "schema_version": 1,
    "elements": [{"type": "input", "name": "str", "id": "str1"}],
}


async def _make_character(
    db_session, owner, system_id="dnd5e", label="Aragorn", name="Strider"
):
    sheet_repository = CharacterSheetRepository(db_session, principal=owner)
    sheet = await sheet_repository.create(
        name="Fighter", system_id=system_id, layout=SHEET_LAYOUT
    )
    version = await sheet_repository.publish(await sheet_repository.get_draft(sheet.id))
    character = await CharacterRepository(db_session, principal=owner).create(
        character_sheet_id=sheet.id,
        character_sheet_version_id=version.id,
        label=label,
    )
    # `name` is normally derived from the sheet's values; set it directly.
    character.name = name
    await db_session.flush()
    return character


async def _put_in_game(db_session, character, game_id, approved=False):
    character.game_id = game_id
    character.approved = approved
    await db_session.flush()


def _payload(**overrides):
    fields = {
        "title": "My Campaign",
        "system_id": "dnd5e",
        "allowed_char_sheets": ["dnd5e"],
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

    async def test_create_game_strips_and_converts_title(
        self, authed_client, system, db_session
    ):
        client, user = authed_client

        response = await client.post(
            "/games/", json=_payload(title="  Line one\nLine two  ")
        )

        assert response.status_code == 200
        game = await db_session.get(Game, response.json()["id"])
        assert game.title == "Line one<br>Line two"
        assert game.gm_id == user.id


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
        assert [p["id"] for p in body["players"]] == [gm.id]
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

    async def test_get_game_as_gm_returns_players_in_all_states(
        self, auth_as, client, db_session, gm, game, create
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

        client = auth_as(gm)
        response = await client.get(f"/games/{game.id}")

        player_user_ids = {p["id"] for p in response.json()["players"]}
        assert player_user_ids == {gm.id, applied.id, accepted.id, invited.id}

    @pytest.mark.parametrize("use_auth", [True, False])
    async def test_get_game_non_gm_only_returns_accepted_players(
        self, client, authed_client, db_session, gm, game, create, use_auth
    ):
        client = authed_client[0] if use_auth else client
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
        assert player_user_ids == {gm.id, accepted.id}

    async def test_get_game_viewer_state_reflects_own_invite(
        self, auth_as, client, db_session, gm, game, create
    ):
        player_repository = PlayerRepository(db_session, principal=gm)
        invitee = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(
            game.id, invitee.id, state=Player.States.INVITED
        )

        client = auth_as(invitee)
        response = await client.get(f"/games/{game.id}")

        body = response.json()
        assert body["viewer_state"] == "invited"
        # The invited player isn't accepted, so they still don't show up in
        # the public players list even though they can see their own state.
        assert [p["id"] for p in body["players"]] == [gm.id]

    async def test_get_game_player_fields(self, client, db_session, gm, game, create):
        user = await create(ActivatedUserFactory)
        await PlayerRepository(db_session, principal=gm).attach_player_to_game(
            game.id, user.id, is_gm=False, state=Player.States.ACCEPTED
        )
        character = await _make_character(db_session, user)
        await _put_in_game(db_session, character, game.id, approved=True)

        response = await client.get(f"/games/{game.id}")

        players = {p["id"]: p for p in response.json()["players"]}
        assert players == {
            gm.id: {
                "id": gm.id,
                "username": gm.username,
                "is_gm": True,
                "state": "accepted",
                "characters": [],
            },
            user.id: {
                "id": user.id,
                "username": user.username,
                "is_gm": False,
                "state": "accepted",
                "characters": [
                    {
                        "id": character.id,
                        "label": "Aragorn",
                        "name": "Strider",
                        "type": "pc",
                        "approved": True,
                        "can_view": False,
                    }
                ],
            },
        }

    @pytest.mark.parametrize("viewer", ["anonymous", "other_player"])
    async def test_get_game_hides_pending_characters_from_others(
        self, auth_as, client, db_session, gm, game, create, viewer
    ):
        player_repository = PlayerRepository(db_session, principal=gm)
        owner = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(
            game.id, owner.id, state=Player.States.ACCEPTED
        )
        approved = await _make_character(db_session, owner, label="Approved")
        await _put_in_game(db_session, approved, game.id, approved=True)
        pending = await _make_character(db_session, owner, label="Pending")
        await _put_in_game(db_session, pending, game.id)
        if viewer == "other_player":
            other = await create(ActivatedUserFactory)
            await player_repository.attach_player_to_game(
                game.id, other.id, state=Player.States.ACCEPTED
            )
            client = auth_as(other)

        response = await client.get(f"/games/{game.id}")

        owner_data = next(p for p in response.json()["players"] if p["id"] == owner.id)
        assert [c["label"] for c in owner_data["characters"]] == ["Approved"]

    @pytest.mark.parametrize("viewer", ["owner", "gm"])
    async def test_get_game_shows_pending_characters_to_owner_and_gm(
        self, auth_as, client, db_session, gm, game, create, viewer
    ):
        player_repository = PlayerRepository(db_session, principal=gm)
        owner = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(
            game.id, owner.id, state=Player.States.ACCEPTED
        )
        pending = await _make_character(db_session, owner, label="Pending")
        await _put_in_game(db_session, pending, game.id)
        client = auth_as(owner if viewer == "owner" else gm)

        response = await client.get(f"/games/{game.id}")

        owner_data = next(p for p in response.json()["players"] if p["id"] == owner.id)
        assert owner_data["characters"] == [
            {
                "id": pending.id,
                "label": "Pending",
                "name": "Strider",
                "type": "pc",
                "approved": False,
                "can_view": True,
            }
        ]

    @pytest.mark.parametrize(
        ("viewer", "expected"),
        [
            ("owner", {"Private": True, "Library": True}),
            ("gm", {"Private": True, "Library": True}),
            ("other_player", {"Private": False, "Library": True}),
            ("anonymous", {"Private": False, "Library": True}),
        ],
    )
    async def test_get_game_character_can_view_depends_on_viewer(
        self, auth_as, client, db_session, gm, game, create, viewer, expected
    ):
        player_repository = PlayerRepository(db_session, principal=gm)
        owner = await create(ActivatedUserFactory)
        other = await create(ActivatedUserFactory)
        for user in (owner, other):
            await player_repository.attach_player_to_game(
                game.id, user.id, state=Player.States.ACCEPTED
            )
        private = await _make_character(db_session, owner, label="Private")
        await _put_in_game(db_session, private, game.id, approved=True)
        library = await _make_character(db_session, owner, label="Library")
        library.in_library = True
        await _put_in_game(db_session, library, game.id, approved=True)
        viewers = {"owner": owner, "gm": gm, "other_player": other}
        if viewer in viewers:
            client = auth_as(viewers[viewer])

        response = await client.get(f"/games/{game.id}")

        owner_data = next(p for p in response.json()["players"] if p["id"] == owner.id)
        assert {c["label"]: c["can_view"] for c in owner_data["characters"]} == expected

    async def test_get_game_favorited_true_when_favorited(self, authed_client, game):
        client, _user = authed_client
        await client.post(f"/games/{game.id}/favorite")

        response = await client.get(f"/games/{game.id}")

        assert response.json()["favorited"] is True


class _GameFixtures:
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
    def make_game(self, db_session, system):
        async def _make_game(gm, title="My Campaign", public=True, system_id=None):
            game_repository = GameRepository(db_session, principal=gm)
            game = await game_repository.create(
                title,
                system_id or system.id,
                [],
                gm.id,
                "3/w",
                4,
                1,
                None,
                None,
                public,
                None,
                None,
            )
            return game

        return _make_game


class TestGetGames(_GameFixtures):
    """GET /games/ - the public "browse games" listing."""

    async def test_get_games_returns_all_games(self, client, gm, make_game, create):
        other_gm = await create(ActivatedUserFactory)
        game_a = await make_game(gm, title="A Game")
        game_b = await make_game(other_gm, title="B Game")

        response = await client.get("/games/")

        game_ids = {g["id"] for g in response.json()["games"]}
        assert game_ids == {game_a.id, game_b.id}

    async def test_get_games_includes_private_games(self, client, gm, make_game):
        game = await make_game(gm, title="Private Game", public=False)

        response = await client.get("/games/")

        games = response.json()["games"]
        assert [g["id"] for g in games] == [game.id]
        assert games[0]["public"] is False

    async def test_get_games_excludes_games_viewer_already_accepted_in(
        self, auth_as, client, gm, make_game, create
    ):
        other_gm = await create(ActivatedUserFactory)
        game_mine = await make_game(gm, title="A Game")
        game_other = await make_game(other_gm, title="B Game")
        client = auth_as(gm)

        response = await client.get("/games/")

        game_ids = {g["id"] for g in response.json()["games"]}
        assert game_ids == {game_other.id}
        assert game_mine.id not in game_ids

    async def test_get_games_includes_games_viewer_only_applied_to(
        self, auth_as, client, db_session, gm, make_game, create
    ):
        game = await make_game(gm, title="A Game")
        applicant = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, applicant.id, state=Player.States.APPLIED
        )
        client = auth_as(applicant)

        response = await client.get("/games/")

        game_ids = {g["id"] for g in response.json()["games"]}
        assert game_ids == {game.id}

    async def test_get_games_search_filters_by_title_case_insensitive(
        self, client, gm, make_game
    ):
        await make_game(gm, title="Curse of Strahd")
        await make_game(gm, title="Tomb of Annihilation")

        response = await client.get("/games/", params={"search": "curse"})

        titles = [g["title"] for g in response.json()["games"]]
        assert titles == ["Curse of Strahd"]

    async def test_get_games_filters_by_multiple_systems(
        self, client, gm, make_game, create
    ):
        other_system = await create(SystemFactory, id="pf2e")
        third_system = await create(SystemFactory, id="swade")
        game_dnd = await make_game(gm, title="A Game")
        game_pf2e = await make_game(gm, title="B Game", system_id=other_system.id)
        await make_game(gm, title="C Game", system_id=third_system.id)

        response = await client.get("/games/", params={"systems": ["dnd5e", "pf2e"]})

        game_ids = {g["id"] for g in response.json()["games"]}
        assert game_ids == {game_dnd.id, game_pf2e.id}

    async def test_get_games_paginates_and_reports_count_and_page(
        self, client, gm, make_game
    ):
        for i in range(configs.PAGINATE_PER_PAGE + 3):
            await make_game(gm, title=f"Game {i:03}")

        first_page = await client.get("/games/", params={"page": 1})
        second_page = await client.get("/games/", params={"page": 2})

        assert len(first_page.json()["games"]) == configs.PAGINATE_PER_PAGE
        assert len(second_page.json()["games"]) == 3
        assert first_page.json()["count"] == configs.PAGINATE_PER_PAGE + 3
        assert first_page.json()["page"] == 1
        assert second_page.json()["page"] == 2
        first_ids = {g["id"] for g in first_page.json()["games"]}
        second_ids = {g["id"] for g in second_page.json()["games"]}
        assert first_ids.isdisjoint(second_ids)

    async def test_get_games_sorted_by_title_ascending(self, client, gm, make_game):
        await make_game(gm, title="Zeta Quest")
        await make_game(gm, title="Alpha Quest")
        await make_game(gm, title="Mid Quest")

        response = await client.get("/games/")

        titles = [g["title"] for g in response.json()["games"]]
        assert titles == ["Alpha Quest", "Mid Quest", "Zeta Quest"]

    async def test_get_games_player_count_counts_accepted_non_gm_only(
        self, client, db_session, gm, make_game, create
    ):
        game = await make_game(gm)
        accepted = await create(ActivatedUserFactory)
        applied = await create(ActivatedUserFactory)
        co_gm = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, accepted.id, state=Player.States.ACCEPTED
        )
        await player_repository.attach_player_to_game(
            game.id, applied.id, state=Player.States.APPLIED
        )
        await player_repository.attach_player_to_game(
            game.id, co_gm.id, is_gm=True, state=Player.States.ACCEPTED
        )

        response = await client.get("/games/")

        # Only "accepted" counts: the primary gm and co_gm are excluded as
        # GMs, and "applied" hasn't been approved yet.
        assert response.json()["games"][0]["player_count"] == 1

    async def test_get_games_favorited_false_when_unauthenticated(
        self, auth_as, client, gm, make_game
    ):
        game = await make_game(gm)
        favorite_client = auth_as(gm)
        await favorite_client.post(f"/games/{game.id}/favorite")
        del favorite_client.headers["Authorization"]

        response = await favorite_client.get("/games/")

        assert response.json()["games"][0]["favorited"] is False

    async def test_get_games_returns_expected_fields(
        self, client, gm, system, make_game
    ):
        game = await make_game(gm, title="My Campaign")

        response = await client.get("/games/")

        assert response.status_code == 200
        body = response.json()["games"][0]
        assert body == {
            "id": game.id,
            "title": "My Campaign",
            "system": system.name,
            "gm": {"id": gm.id, "username": gm.username},
            "post_frequency": {"times_per": 3, "per_period": "w"},
            "num_players": 4,
            "player_count": 0,
            "forum_id": game.root_forum_id,
            "is_retired": False,
            "status": "open",
            "public": True,
            "favorited": False,
        }


class TestGetLatestGames(_GameFixtures):
    """GET /games/latest - the landing page's newest games for one system."""

    @pytest.fixture
    def make_dated_game(self, db_session, make_game):
        # Every game in a test shares one transaction, and Postgres now() is
        # the transaction's start time, so `created` must be set explicitly
        # for ordering to be observable.
        async def _make_dated_game(gm, days_ago, **kwargs):
            game = await make_game(gm, **kwargs)
            game.created = datetime.now(timezone.utc) - timedelta(days=days_ago)
            await db_session.flush()
            return game

        return _make_dated_game

    async def test_get_latest_games_returns_three_newest_first(
        self, client, gm, make_dated_game
    ):
        await make_dated_game(gm, days_ago=4, title="Oldest")
        third = await make_dated_game(gm, days_ago=3)
        newest = await make_dated_game(gm, days_ago=1)
        second = await make_dated_game(gm, days_ago=2)

        response = await client.get("/games/latest", params={"system": "dnd5e"})

        game_ids = [g["id"] for g in response.json()["games"]]
        assert game_ids == [newest.id, second.id, third.id]

    async def test_get_latest_games_filters_by_system(
        self, client, gm, make_game, create
    ):
        other_system = await create(SystemFactory, id="pf2e")
        game = await make_game(gm)
        await make_game(gm, system_id=other_system.id)

        response = await client.get("/games/latest", params={"system": "dnd5e"})

        assert [g["id"] for g in response.json()["games"]] == [game.id]

    async def test_get_latest_games_without_system_spans_all_systems(
        self, client, gm, make_game, create
    ):
        other_system = await create(SystemFactory, id="pf2e")
        game_dnd = await make_game(gm)
        game_pf2e = await make_game(gm, system_id=other_system.id)

        response = await client.get("/games/latest")

        game_ids = {g["id"] for g in response.json()["games"]}
        assert game_ids == {game_dnd.id, game_pf2e.id}

    async def test_get_latest_games_excludes_retired_games(
        self, client, db_session, gm, make_game
    ):
        game = await make_game(gm)
        retired = await make_game(gm)
        await GameRepository(db_session, principal=gm).toggle_retire(retired)

        response = await client.get("/games/latest", params={"system": "dnd5e"})

        assert [g["id"] for g in response.json()["games"]] == [game.id]

    async def test_get_latest_games_includes_viewers_own_games(
        self, auth_as, client, gm, make_game
    ):
        game = await make_game(gm)
        client = auth_as(gm)

        response = await client.get("/games/latest", params={"system": "dnd5e"})

        assert [g["id"] for g in response.json()["games"]] == [game.id]

    async def test_exclude_mine_drops_the_principals_games(
        self, auth_as, client, db_session, gm, make_game, create
    ):
        viewer = await create(ActivatedUserFactory)
        open_game = await make_game(gm, title="Open")
        joined = await make_game(gm, title="Joined")
        await PlayerRepository(db_session, principal=gm).attach_player_to_game(
            joined.id, viewer.id, state=Player.States.ACCEPTED
        )
        client = auth_as(viewer)

        response = await client.get("/games/latest", params={"exclude_mine": True})

        assert [g["id"] for g in response.json()["games"]] == [open_game.id]

    async def test_exclude_mine_does_nothing_for_guests(self, client, gm, make_game):
        game = await make_game(gm)

        response = await client.get("/games/latest", params={"exclude_mine": True})

        assert [g["id"] for g in response.json()["games"]] == [game.id]


class TestGetMyGames(_GameFixtures):
    """GET /games/my - the authenticated "My Games" listing."""

    async def test_get_my_games_excludes_other_users_games(
        self, auth_as, client, gm, make_game, create
    ):
        other_gm = await create(ActivatedUserFactory)
        await make_game(other_gm)
        client = auth_as(gm)

        response = await client.get("/games/my")

        assert response.json()["games"] == []

    async def test_get_my_games_includes_gm_games(self, auth_as, client, gm, make_game):
        game = await make_game(gm)
        client = auth_as(gm)

        response = await client.get("/games/my")

        game_ids = {g["id"] for g in response.json()["games"]}
        assert game_ids == {game.id}

    async def test_get_my_games_includes_accepted_player_games(
        self, auth_as, client, db_session, gm, make_game, create
    ):
        game = await make_game(gm)
        player = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, player.id, state=Player.States.ACCEPTED
        )
        client = auth_as(player)

        response = await client.get("/games/my")

        game_ids = {g["id"] for g in response.json()["games"]}
        assert game_ids == {game.id}

    async def test_get_my_games_excludes_applied_and_invited_games(
        self, auth_as, client, db_session, gm, make_game, create
    ):
        game = await make_game(gm)
        applicant = await create(ActivatedUserFactory)
        invitee = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, applicant.id, state=Player.States.APPLIED
        )
        await player_repository.attach_player_to_game(
            game.id, invitee.id, state=Player.States.INVITED
        )

        applicant_response = await auth_as(applicant).get("/games/my")
        invitee_response = await auth_as(invitee).get("/games/my")

        assert applicant_response.json()["games"] == []
        assert invitee_response.json()["games"] == []

    async def test_get_my_games_is_not_paginated(
        self, auth_as, client, db_session, gm, make_game, create
    ):
        # "My Games" groups the full list into playing/running/retired
        # sections client-side, so it must never be truncated by pagination.
        player = await create(ActivatedUserFactory)
        for i in range(configs.PAGINATE_PER_PAGE + 5):
            game = await make_game(gm, title=f"Game {i}")
            player_repository = PlayerRepository(db_session, principal=gm)
            await player_repository.attach_player_to_game(
                game.id, player.id, state=Player.States.ACCEPTED
            )
        client = auth_as(player)

        response = await client.get("/games/my")

        assert len(response.json()["games"]) == configs.PAGINATE_PER_PAGE + 5

    async def test_get_my_games_per_game_fields_are_not_cross_contaminated(
        self, auth_as, client, db_session, gm, make_game, create
    ):
        # A regression guard for the bulk per-game lookups (player_counts,
        # gm_game_ids, favorited_ids): each is keyed by game id, so a game
        # the viewer doesn't GM/favorite must not pick up flags that belong
        # to a different game in the same response.
        other_gm = await create(ActivatedUserFactory)
        await make_game(gm, title="Game A")
        game_b = await make_game(other_gm, title="Game B")
        player_repository = PlayerRepository(db_session, principal=other_gm)
        await player_repository.attach_player_to_game(
            game_b.id, gm.id, state=Player.States.ACCEPTED
        )
        client = auth_as(gm)
        await client.post(f"/games/{game_b.id}/favorite")

        response = await client.get("/games/my")

        games = response.json()["games"]
        assert [g["title"] for g in games] == ["Game A", "Game B"]
        assert games[0]["is_gm"] is True
        assert games[0]["favorited"] is False
        assert games[0]["player_count"] == 0
        assert games[1]["is_gm"] is False
        assert games[1]["favorited"] is True
        assert games[1]["player_count"] == 1

    async def test_get_my_games_orders_by_last_activity_then_title(
        self, auth_as, client, db_session, create, gm, make_game
    ):
        older = await make_game(gm, title="Older")
        newer = await make_game(gm, title="Newer")
        await make_game(gm, title="Zeta quiet")
        await make_game(gm, title="Alpha quiet")
        threads = {}
        for game, hours in ((older, 5), (newer, 1)):
            forum = await db_session.get(Forum, game.root_forum_id)
            threads[game.id] = await add_thread(create, db_session, forum, hours=hours)
        client = auth_as(gm)

        response = await client.get("/games/my")

        games = response.json()["games"]
        assert [g["title"] for g in games] == [
            "Newer",
            "Older",
            "Alpha quiet",
            "Zeta quiet",
        ]
        assert (
            datetime.fromisoformat(games[0]["last_activity"])
            == threads[newer.id].last_post_at
        )
        assert games[2]["last_activity"] is None

    async def test_get_my_games_has_unread_follows_the_games_forum_threads(
        self, auth_as, client, db_session, create, gm, make_game
    ):
        unread = await make_game(gm, title="Unread")
        read = await make_game(gm, title="Read")
        await make_game(gm, title="Quiet")
        await add_thread(
            create, db_session, await db_session.get(Forum, unread.root_forum_id)
        )
        read_thread = await add_thread(
            create, db_session, await db_session.get(Forum, read.root_forum_id)
        )
        await ReadTrackingRepository(db_session, principal=gm).mark_thread_read(
            read_thread
        )
        client = auth_as(gm)

        response = await client.get("/games/my")

        flags = {g["title"]: g["has_unread"] for g in response.json()["games"]}
        assert flags == {"Unread": True, "Read": False, "Quiet": False}

    async def test_get_my_games_has_unread_rolls_up_readable_subforums_only(
        self, auth_as, client, db_session, create, gm, make_game
    ):
        rolled_up = await make_game(gm, title="Rolled up")
        hidden = await make_game(gm, title="Hidden")
        for game in (rolled_up, hidden):
            root = await db_session.get(Forum, game.root_forum_id)
            subforum = await create(
                ForumFactory,
                parent_id=root.id,
                heritage=[*root.heritage, root.id],
                game_id=game.id,
            )
            await add_thread(create, db_session, subforum)
        # A deny on the last (Hidden's) subforum overrides what the GM gets from
        # its root.
        denial = RoleFactory.build()
        db_session.add(denial)
        for verb in (Verbs.FORUM_READ, Verbs.FORUM_MODERATE):
            denial.grant(
                verb,
                scope_type=RolePermission.ScopeTypes.FORUM,
                scope_id=subforum.id,
                effect=RolePermission.Effects.DENY,
            )
        denial.users.append(gm)
        await db_session.flush()
        client = auth_as(gm)

        response = await client.get("/games/my")

        flags = {g["title"]: g["has_unread"] for g in response.json()["games"]}
        assert flags == {"Rolled up": True, "Hidden": False}

    async def test_get_my_games_is_gm_true_for_delegated_co_gm(
        self, auth_as, client, db_session, gm, make_game, create
    ):
        game = await make_game(gm)
        co_gm = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, co_gm.id, is_gm=True, state=Player.States.ACCEPTED
        )
        client = auth_as(co_gm)

        response = await client.get("/games/my")

        assert response.json()["games"][0]["is_gm"] is True

    async def test_get_my_games_reflects_retired_and_closed(
        self, auth_as, client, gm, make_game
    ):
        game = await make_game(gm)
        client = auth_as(gm)
        # Retiring also closes the game, so both fields come from one request.
        await client.patch(f"/games/{game.id}/retire")

        response = await client.get("/games/my")

        entry = response.json()["games"][0]
        assert entry["is_retired"] is True
        assert entry["status"] == "closed"


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

    async def test_update_game_not_gm_forbidden(self, authed_client, game):
        client, _user = authed_client

        response = await client.patch(f"/games/{game.id}", json=_payload())

        assert response.status_code == 403

    async def test_update_game_as_gm_updates_fields(
        self, auth_as, client, db_session, game, gm
    ):
        client = auth_as(gm)

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

    async def test_update_game_allowed_char_sheets(
        self, auth_as, client, db_session, game, gm, create
    ):
        client = auth_as(gm)
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

    async def test_update_game_system_not_found(self, auth_as, client, game, gm):
        client = auth_as(gm)

        response = await client.patch(
            f"/games/{game.id}", json=_payload(system_id="does-not-exist")
        )

        assert response.status_code == 404

    async def test_update_game_allowed_char_sheet_not_found(
        self, auth_as, client, game, gm
    ):
        client = auth_as(gm)

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

    async def test_favorite_game_not_found(self, authed_client):
        client, _user = authed_client

        response = await client.post("/games/999999/favorite")

        assert response.status_code == 404

    async def test_favorite_game_toggles_favorite(
        self, authed_client, game, db_session
    ):
        client, user = authed_client

        response = await client.post(f"/games/{game.id}/favorite")

        assert response.status_code == 200
        assert response.json() == {"favorite": True}
        favorite = await db_session.get(FavoriteGame, (user.id, game.id))
        assert favorite is not None

        response = await client.post(f"/games/{game.id}/favorite")

        assert response.status_code == 200
        assert response.json() == {"favorite": False}
        favorite = await db_session.get(FavoriteGame, (user.id, game.id))
        assert favorite is None


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
        return game

    async def test_invite_player_not_gm_forbidden(self, authed_client, game):
        client, _user = authed_client

        response = await client.post(
            f"/games/{game.id}/invite", json={"username": "someone"}
        )

        assert response.status_code == 403

    async def test_invite_player_user_not_found(self, auth_as, client, game, gm):
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/invite", json={"username": "does-not-exist"}
        )

        assert response.status_code == 404

    async def test_invite_player_creates_invited_player(
        self, auth_as, client, db_session, game, gm, create
    ):
        client = auth_as(gm)
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
        self, auth_as, client, db_session, game, gm, create
    ):
        client = auth_as(gm)
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
        return game

    async def test_apply_to_game_closed_forbidden(
        self, auth_as, client, db_session, game, gm, create
    ):
        game_repository = GameRepository(db_session, principal=gm)
        await game_repository.update(game, status=Game.Statuses.CLOSED)
        applicant = await create(ActivatedUserFactory)
        client = auth_as(applicant)

        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 403

    async def test_apply_to_game_not_public_forbidden(
        self, auth_as, client, db_session, game, gm, create
    ):
        game_repository = GameRepository(db_session, principal=gm)
        await game_repository.update(game, public=False)
        applicant = await create(ActivatedUserFactory)
        client = auth_as(applicant)

        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 403

    async def test_apply_to_game_creates_applied_player(
        self, auth_as, client, db_session, game, create
    ):
        applicant = await create(ActivatedUserFactory)
        client = auth_as(applicant)

        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 204
        player = await db_session.get(
            Player, {"game_id": game.id, "user_id": applicant.id}
        )
        assert player is not None
        assert player.state == Player.States.APPLIED
        assert player.is_gm is False

    async def test_apply_to_game_apply_twice_conflict(
        self, auth_as, client, db_session, game, create
    ):
        applicant = await create(ActivatedUserFactory)
        client = auth_as(applicant)
        await client.post(f"/games/{game.id}/apply")

        response = await client.post(f"/games/{game.id}/apply")

        assert response.status_code == 409
        # The test client's db_session override bypasses the commit/rollback
        # that DBSessionDependency normally does at the request boundary, so
        # the failed flush's rolled-back transaction state must be cleared
        # manually or it poisons every later test sharing this session.
        await db_session.rollback()


class TestApprovePlayer:
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
        return game

    async def test_approve_player_not_in_game_not_found(
        self, auth_as, client, game, gm, create
    ):
        client = auth_as(gm)
        stranger = await create(ActivatedUserFactory)

        response = await client.post(f"/games/{game.id}/player/{stranger.id}/approve")

        assert response.status_code == 404

    async def test_approve_player_already_accepted_conflict(
        self, auth_as, client, game, gm
    ):
        client = auth_as(gm)

        response = await client.post(f"/games/{game.id}/player/{gm.id}/approve")

        assert response.status_code == 409

    async def test_approve_player_accepts_player(
        self, auth_as, client, db_session, game, gm, create
    ):
        target = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, target.id, state=Player.States.APPLIED
        )
        client = auth_as(gm)

        response = await client.post(f"/games/{game.id}/player/{target.id}/approve")

        assert response.status_code == 204
        player = await db_session.get(
            Player, {"game_id": game.id, "user_id": target.id}
        )
        assert player.state == Player.States.ACCEPTED

    async def test_approve_player_starts_game_forums_read(
        self, auth_as, client, db_session, game, gm, create
    ):
        root_forum = await db_session.get(Forum, game.root_forum_id)
        thread = await create(
            ThreadFactory,
            forum=root_forum,
            last_post_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        target = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, target.id, state=Player.States.APPLIED
        )
        read_tracking = ReadTrackingRepository(db_session, principal=target)
        assert await read_tracking.is_thread_unread(thread)
        client = auth_as(gm)

        response = await client.post(f"/games/{game.id}/player/{target.id}/approve")

        assert response.status_code == 204
        assert not await read_tracking.is_thread_unread(thread)


class TestAcceptInvite:
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
        return game

    async def test_accept_invite_not_invited_conflict(
        self, auth_as, client, db_session, game, gm, create
    ):
        applicant = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, applicant.id, state=Player.States.APPLIED
        )
        client = auth_as(applicant)

        response = await client.post(f"/games/{game.id}/accept_invite")

        assert response.status_code == 409

    async def test_accept_invite_accepts_own_invite(
        self, auth_as, client, db_session, game, gm, create
    ):
        invitee = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, invitee.id, state=Player.States.INVITED
        )
        client = auth_as(invitee)

        response = await client.post(f"/games/{game.id}/accept_invite")

        assert response.status_code == 204
        player = await db_session.get(
            Player, {"game_id": game.id, "user_id": invitee.id}
        )
        assert player.state == Player.States.ACCEPTED


class TestToggleGm:
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
        return game

    @pytest.fixture
    async def accepted_player(self, db_session, gm, game, create):
        target = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, target.id, state=Player.States.ACCEPTED
        )
        return target

    async def test_toggle_gm_primary_gm_forbidden(self, auth_as, client, game, gm):
        client = auth_as(gm)

        response = await client.post(f"/games/{game.id}/player/{gm.id}/toggle_gm")

        assert response.status_code == 403

    async def test_toggle_gm_unaccepted_player_conflict(
        self, auth_as, client, db_session, game, gm, create
    ):
        client = auth_as(gm)
        target = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, target.id, state=Player.States.APPLIED
        )

        response = await client.post(f"/games/{game.id}/player/{target.id}/toggle_gm")

        assert response.status_code == 409
        player = await db_session.get(
            Player, {"game_id": game.id, "user_id": target.id}
        )
        assert player.is_gm is False

    async def test_toggle_gm_promotes_player(
        self, auth_as, client, db_session, game, gm, accepted_player
    ):
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/player/{accepted_player.id}/toggle_gm"
        )

        assert response.status_code == 204
        player = await db_session.get(
            Player, {"game_id": game.id, "user_id": accepted_player.id}
        )
        assert player.is_gm is True

    async def test_toggle_gm_twice_demotes_player(
        self, auth_as, client, db_session, game, gm, accepted_player
    ):
        client = auth_as(gm)
        await client.post(f"/games/{game.id}/player/{accepted_player.id}/toggle_gm")

        response = await client.post(
            f"/games/{game.id}/player/{accepted_player.id}/toggle_gm"
        )

        assert response.status_code == 204
        player = await db_session.get(
            Player, {"game_id": game.id, "user_id": accepted_player.id}
        )
        assert player.is_gm is False


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

    async def test_toggle_game_flag_not_gm_forbidden(self, authed_client, game):
        client, _user = authed_client

        response = await client.patch(f"/games/{game.id}/toggle/public")

        assert response.status_code == 403

    async def test_toggle_public_flips_the_flag_both_ways(
        self, auth_as, client, game, gm, db_session
    ):
        client = auth_as(gm)
        assert game.public is True

        response = await client.patch(f"/games/{game.id}/toggle/public")

        assert response.status_code == 204
        game = await db_session.get(Game, game.id)
        assert game.public is False

        response = await client.patch(f"/games/{game.id}/toggle/public")

        assert response.status_code == 204
        game = await db_session.get(Game, game.id)
        assert game.public is True

    async def test_toggle_status_flips_the_flag_both_ways(
        self, auth_as, client, game, gm, db_session
    ):
        client = auth_as(gm)
        assert game.status == Game.Statuses.OPEN

        response = await client.patch(f"/games/{game.id}/toggle/status")

        assert response.status_code == 204
        game = await db_session.get(Game, game.id)
        assert game.status == Game.Statuses.CLOSED

        response = await client.patch(f"/games/{game.id}/toggle/status")

        assert response.status_code == 204
        game = await db_session.get(Game, game.id)
        assert game.status == Game.Statuses.OPEN


class TestToggleRetireGame:
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

    async def test_toggle_retire_game_co_gm_forbidden(
        self, auth_as, client, game, gm, create, db_session
    ):
        co_gm = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, co_gm.id, is_gm=True, state=Player.States.ACCEPTED
        )
        client = auth_as(co_gm)

        response = await client.patch(f"/games/{game.id}/retire")

        assert response.status_code == 403

    async def test_toggle_retire_game_retires_the_game(
        self, auth_as, client, game, gm, db_session
    ):
        client = auth_as(gm)
        assert game.retired is None
        assert game.status == Game.Statuses.OPEN

        response = await client.patch(f"/games/{game.id}/retire")

        assert response.status_code == 204
        game = await db_session.get(Game, game.id)
        assert game.retired is not None
        assert game.status == Game.Statuses.CLOSED

    async def test_toggle_retire_game_twice_unretires_but_stays_closed(
        self, auth_as, client, game, gm, db_session
    ):
        client = auth_as(gm)
        await client.patch(f"/games/{game.id}/retire")

        response = await client.patch(f"/games/{game.id}/retire")

        assert response.status_code == 204
        game = await db_session.get(Game, game.id)
        assert game.retired is None
        assert game.status == Game.Statuses.CLOSED


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
        return game

    @pytest.fixture
    async def invitee(self, db_session, gm, game, create):
        invitee = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, invitee.id, state=Player.States.INVITED
        )
        return invitee

    async def test_delete_player_not_gm_and_not_self_forbidden(
        self, authed_client, game, invitee
    ):
        client, _user = authed_client

        response = await client.delete(f"/games/{game.id}/player/{invitee.id}")

        assert response.status_code == 403

    async def test_delete_player_as_gm_removes_player(
        self, auth_as, client, db_session, game, gm, create
    ):
        target = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, target.id, state=Player.States.ACCEPTED
        )
        client = auth_as(gm)

        response = await client.delete(f"/games/{game.id}/player/{target.id}")

        assert response.status_code == 204
        player = await db_session.get(
            Player, {"game_id": game.id, "user_id": target.id}
        )
        assert player is None

    async def test_delete_player_as_self_removes_own_player(
        self, auth_as, client, db_session, game, gm, create
    ):
        target = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, target.id, state=Player.States.ACCEPTED
        )
        client = auth_as(target)

        response = await client.delete(f"/games/{game.id}/player/{target.id}")

        assert response.status_code == 204
        player = await db_session.get(
            Player, {"game_id": game.id, "user_id": target.id}
        )
        assert player is None

    async def test_delete_player_not_in_game_not_found(
        self, auth_as, client, game, gm, create
    ):
        client = auth_as(gm)
        stranger = await create(ActivatedUserFactory)

        response = await client.delete(f"/games/{game.id}/player/{stranger.id}")

        assert response.status_code == 404

    async def test_delete_player_primary_gm_forbidden(self, auth_as, client, game, gm):
        client = auth_as(gm)

        response = await client.delete(f"/games/{game.id}/player/{gm.id}")

        assert response.status_code == 403

    async def test_delete_player_takes_their_characters_out_of_the_game(
        self, auth_as, client, db_session, game, gm, create
    ):
        player = await create(ActivatedUserFactory)
        await PlayerRepository(db_session, principal=gm).attach_player_to_game(
            game.id, player.id, state=Player.States.ACCEPTED
        )
        approved = await _make_character(db_session, player)
        await _put_in_game(db_session, approved, game.id, approved=True)
        pending = await _make_character(db_session, player)
        await _put_in_game(db_session, pending, game.id)
        gm_character = await _make_character(db_session, gm)
        await _put_in_game(db_session, gm_character, game.id, approved=True)
        client = auth_as(gm)

        response = await client.delete(f"/games/{game.id}/player/{player.id}")

        assert response.status_code == 204
        for character in (approved, pending, gm_character):
            await db_session.refresh(character)
        assert (approved.game_id, approved.approved) == (None, False)
        assert (pending.game_id, pending.approved) == (None, False)
        assert gm_character.game_id == game.id


class TestCreateDeck:
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
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

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
        return game

    def _payload(self, deck_type, **overrides):
        fields = {
            "label": "Fate Deck",
            "type": deck_type.short,
            "permissions": [],
        }
        fields.update(overrides)
        return fields

    async def test_create_deck_permission_target_must_be_accepted(
        self, auth_as, client, db_session, game, gm, deck_type, create
    ):
        client = auth_as(gm)
        applicant = await create(ActivatedUserFactory)
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, applicant.id, state=Player.States.APPLIED
        )

        response = await client.post(
            f"/games/{game.id}/decks",
            json=self._payload(deck_type, permissions=[applicant.id]),
        )

        assert response.status_code == 404

    async def test_create_deck_creates_deck(
        self, auth_as, client, db_session, game, gm, deck_type
    ):
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/decks", json=self._payload(deck_type)
        )

        assert response.status_code == 200
        deck = await db_session.get(Deck, response.json()["id"])
        assert deck is not None
        assert deck.game_id == game.id
        assert deck.label == "Fate Deck"
        assert deck.type_id == deck_type.short
        assert deck.position == 0


class TestGetDecks:
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
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

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

    async def test_get_decks_returns_decks_for_game(
        self, auth_as, client, db_session, gm, game, deck_type, create
    ):
        client = auth_as(gm)
        deck_repository = DeckRepository(db_session, principal=gm)
        player = await create(ActivatedUserFactory)
        deck = await deck_repository.create(
            game_id=game.id,
            label="Fate Deck",
            type=deck_type.short,
            permissions=[player.id],
        )

        response = await client.get(f"/games/{game.id}/decks")

        assert response.status_code == 200
        body = response.json()
        assert len(body["decks"]) == 1
        assert body["decks"][0] == {
            "id": deck.id,
            "label": "Fate Deck",
            "type": deck_type.short,
            "size": deck_type.deck_size,
            "position": 0,
            "permissions": [player.id],
        }


class TestGetDeck:
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
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

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

    @pytest.fixture
    async def deck(self, db_session, gm, game, deck_type):
        deck_repository = DeckRepository(db_session, principal=gm)
        return await deck_repository.create(
            game_id=game.id,
            label="Fate Deck",
            type=deck_type.short,
            permissions=[],
        )

    async def test_get_deck_not_found(self, auth_as, client, gm, game):
        client = auth_as(gm)

        response = await client.get(f"/games/{game.id}/decks/999999")

        assert response.status_code == 404

    async def test_get_deck_belonging_to_another_game_not_found(
        self, auth_as, client, db_session, gm, game, system, deck_type
    ):
        client = auth_as(gm)
        game_repository = GameRepository(db_session, principal=gm)
        other_game = await game_repository.create(
            "Other Campaign",
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
        deck_repository = DeckRepository(db_session, principal=gm)
        other_deck = await deck_repository.create(
            game_id=other_game.id,
            label="Other Deck",
            type=deck_type.short,
            permissions=[],
        )

        response = await client.get(f"/games/{game.id}/decks/{other_deck.id}")

        assert response.status_code == 404

    async def test_get_deck_returns_deck(
        self, auth_as, client, gm, game, deck, deck_type
    ):
        client = auth_as(gm)

        response = await client.get(f"/games/{game.id}/decks/{deck.id}")

        assert response.status_code == 200
        assert response.json() == {
            "deck": {
                "id": deck.id,
                "label": "Fate Deck",
                "type": deck_type.short,
                "size": deck_type.deck_size,
                "position": 0,
                "permissions": [],
            }
        }


class TestUpdateDeck:
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
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

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
        return game

    @pytest.fixture
    async def deck(self, db_session, gm, game, deck_type):
        deck_repository = DeckRepository(db_session, principal=gm)
        return await deck_repository.create(
            game_id=game.id,
            label="Fate Deck",
            type=deck_type.short,
            permissions=[],
        )

    def _payload(self, deck_type, **overrides):
        fields = {
            "label": "Fate Deck",
            "type": deck_type.short,
            "permissions": [],
        }
        fields.update(overrides)
        return fields

    async def test_update_deck_permission_user_not_in_game_not_found(
        self, auth_as, client, game, gm, deck, deck_type, create
    ):
        client = auth_as(gm)
        stranger = await create(ActivatedUserFactory)

        response = await client.patch(
            f"/games/{game.id}/decks/{deck.id}",
            json=self._payload(deck_type, permissions=[stranger.id]),
        )

        assert response.status_code == 404

    async def test_update_deck_updates_label_and_permissions(
        self, auth_as, client, db_session, game, gm, deck, deck_type, create
    ):
        client = auth_as(gm)
        player_repository = PlayerRepository(db_session, principal=gm)
        old_player = await create(ActivatedUserFactory)
        new_player = await create(ActivatedUserFactory)
        await player_repository.attach_player_to_game(
            game.id, old_player.id, state=Player.States.ACCEPTED
        )
        await player_repository.attach_player_to_game(
            game.id, new_player.id, state=Player.States.ACCEPTED
        )
        deck_repository = DeckRepository(db_session, principal=gm)
        await deck_repository.update(
            deck, label=deck.label, type=deck_type.short, permissions=[old_player.id]
        )

        response = await client.patch(
            f"/games/{game.id}/decks/{deck.id}",
            json=self._payload(
                deck_type, label="Renamed Deck", permissions=[new_player.id]
            ),
        )

        assert response.status_code == 200
        await db_session.refresh(deck)
        assert deck.label == "Renamed Deck"
        permissions = await db_session.scalars(
            select(DeckPermission).where(DeckPermission.deck_id == deck.id)
        )
        assert {p.user_id for p in permissions} == {new_player.id}


class TestShuffleDeck:
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
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

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
        return game

    @pytest.fixture
    async def deck(self, db_session, gm, game, deck_type):
        deck_repository = DeckRepository(db_session, principal=gm)
        return await deck_repository.create(
            game_id=game.id,
            label="Fate Deck",
            type=deck_type.short,
            permissions=[],
        )

    async def test_shuffle_deck_reshuffles(
        self, auth_as, client, db_session, game, gm, deck, deck_type
    ):
        client = auth_as(gm)
        original_shuffled_at = deck.last_shuffled

        response = await client.patch(f"/games/{game.id}/decks/{deck.id}/shuffle")

        assert response.status_code == 204
        await db_session.refresh(deck)
        assert deck.last_shuffled > original_shuffled_at
        assert set(deck.order) == set(range(deck_type.deck_size))


class TestDeleteDeck:
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
    async def deck_type(self, create):
        return await create(DeckTypeFactory, deck_size=52)

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
        return game

    @pytest.fixture
    async def deck(self, db_session, gm, game, deck_type):
        deck_repository = DeckRepository(db_session, principal=gm)
        return await deck_repository.create(
            game_id=game.id,
            label="Fate Deck",
            type=deck_type.short,
            permissions=[],
        )

    async def test_delete_deck_removes_deck(
        self, auth_as, client, db_session, game, gm, deck
    ):
        client = auth_as(gm)

        response = await client.delete(f"/games/{game.id}/decks/{deck.id}")

        assert response.status_code == 204
        assert await db_session.get(Deck, deck.id) is None


class _GameCharacterFixtures:
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
            [system.id],
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
        return game

    @pytest.fixture
    async def player(self, db_session, create, game, gm):
        player = await create(ActivatedUserFactory)
        await PlayerRepository(db_session, principal=gm).attach_player_to_game(
            game.id, player.id, state=Player.States.ACCEPTED
        )
        return player


class TestSubmitCharacter(_GameCharacterFixtures):
    async def test_retired_game_forbidden(
        self, auth_as, client, db_session, game, gm, player
    ):
        await GameRepository(db_session, principal=gm).toggle_retire(game)
        character = await _make_character(db_session, player)
        client = auth_as(player)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": character.id}
        )

        assert response.status_code == 403

    async def test_non_player_forbidden(
        self, auth_as, client, db_session, create, game
    ):
        stranger = await create(ActivatedUserFactory)
        character = await _make_character(db_session, stranger)
        client = auth_as(stranger)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": character.id}
        )

        assert response.status_code == 403

    async def test_player_not_yet_accepted_forbidden(
        self, auth_as, client, db_session, create, game, gm
    ):
        applicant = await create(ActivatedUserFactory)
        await PlayerRepository(db_session, principal=gm).attach_player_to_game(
            game.id, applicant.id, state=Player.States.APPLIED
        )
        character = await _make_character(db_session, applicant)
        client = auth_as(applicant)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": character.id}
        )

        assert response.status_code == 403

    async def test_character_not_found(self, auth_as, client, game, player):
        client = auth_as(player)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": 999999}
        )

        assert response.status_code == 404

    async def test_someone_elses_character_forbidden(
        self, auth_as, client, db_session, create, game, player
    ):
        stranger = await create(ActivatedUserFactory)
        character = await _make_character(db_session, stranger)
        client = auth_as(player)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": character.id}
        )

        assert response.status_code == 403

    async def test_character_already_in_a_game_conflict(
        self, auth_as, client, db_session, game, gm, player
    ):
        other_game = await GameRepository(db_session, principal=gm).create(
            "Other Campaign",
            "dnd5e",
            ["dnd5e"],
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
        character = await _make_character(db_session, player)
        await _put_in_game(db_session, character, other_game.id)
        client = auth_as(player)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": character.id}
        )

        assert response.status_code == 409

    async def test_sheet_system_not_allowed(
        self, auth_as, client, db_session, create, game, player
    ):
        await create(SystemFactory, id="pf2e")
        character = await _make_character(db_session, player, system_id="pf2e")
        client = auth_as(player)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": character.id}
        )

        assert response.status_code == 400

    @pytest.mark.parametrize("name", [None, "", "   "])
    async def test_nameless_character_rejected(
        self, auth_as, client, db_session, game, player, name
    ):
        character = await _make_character(db_session, player, name=name)
        client = auth_as(player)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": character.id}
        )

        assert response.status_code == 400
        await db_session.refresh(character)
        assert character.game_id is None

    async def test_player_at_character_limit_forbidden(
        self, auth_as, client, db_session, game, player
    ):
        first = await _make_character(db_session, player)
        await _put_in_game(db_session, first, game.id, approved=True)
        second = await _make_character(db_session, player)
        client = auth_as(player)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": second.id}
        )

        assert response.status_code == 403

    async def test_pending_characters_dont_count_toward_limit(
        self, auth_as, client, db_session, game, player
    ):
        first = await _make_character(db_session, player)
        await _put_in_game(db_session, first, game.id)
        second = await _make_character(db_session, player)
        client = auth_as(player)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": second.id}
        )

        assert response.status_code == 204

    async def test_gm_is_not_held_to_character_limit(
        self, auth_as, client, db_session, game, gm
    ):
        first = await _make_character(db_session, gm)
        await _put_in_game(db_session, first, game.id, approved=True)
        second = await _make_character(db_session, gm)
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": second.id}
        )

        assert response.status_code == 204

    async def test_submits_character_pending_approval(
        self, auth_as, client, db_session, game, player
    ):
        character = await _make_character(db_session, player)
        client = auth_as(player)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": character.id}
        )

        assert response.status_code == 204
        await db_session.refresh(character)
        assert character.game_id == game.id
        assert character.approved is False

    async def test_gm_submission_is_approved(
        self, auth_as, client, db_session, game, gm
    ):
        character = await _make_character(db_session, gm)
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/characters", json={"character_id": character.id}
        )

        assert response.status_code == 204
        await db_session.refresh(character)
        assert character.game_id == game.id
        assert character.approved is True


class TestApproveCharacter(_GameCharacterFixtures):
    @pytest.fixture
    async def pending(self, db_session, game, player):
        character = await _make_character(db_session, player)
        await _put_in_game(db_session, character, game.id)
        return character

    async def test_already_approved_conflict(
        self, auth_as, client, db_session, game, gm, pending
    ):
        pending.approved = True
        await db_session.flush()
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/characters/{pending.id}/approve"
        )

        assert response.status_code == 409

    @pytest.mark.parametrize("name", [None, "", "   "])
    async def test_nameless_character_rejected(
        self, auth_as, client, db_session, game, gm, pending, name
    ):
        pending.name = name
        await db_session.flush()
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/characters/{pending.id}/approve"
        )

        assert response.status_code == 400
        await db_session.refresh(pending)
        assert pending.approved is False

    async def test_approves_character(
        self, auth_as, client, db_session, game, gm, pending
    ):
        client = auth_as(gm)

        response = await client.post(
            f"/games/{game.id}/characters/{pending.id}/approve"
        )

        assert response.status_code == 204
        await db_session.refresh(pending)
        assert pending.approved is True


class TestRemoveCharacter(_GameCharacterFixtures):
    @pytest.fixture
    async def character(self, db_session, game, player):
        character = await _make_character(db_session, player)
        await _put_in_game(db_session, character, game.id, approved=True)
        return character

    async def test_other_player_forbidden(
        self, auth_as, client, db_session, create, game, gm, character
    ):
        other = await create(ActivatedUserFactory)
        await PlayerRepository(db_session, principal=gm).attach_player_to_game(
            game.id, other.id, state=Player.States.ACCEPTED
        )
        client = auth_as(other)

        response = await client.delete(f"/games/{game.id}/characters/{character.id}")

        assert response.status_code == 403

    @pytest.mark.parametrize("remover", ["owner", "gm"])
    async def test_removes_character_from_game(
        self, auth_as, client, db_session, game, gm, player, character, remover
    ):
        client = auth_as(player if remover == "owner" else gm)

        response = await client.delete(f"/games/{game.id}/characters/{character.id}")

        assert response.status_code == 204
        await db_session.refresh(character)
        assert (character.game_id, character.approved) == (None, False)


class TestCharacterInAnotherGame(_GameCharacterFixtures):
    @pytest.mark.parametrize(
        ("method", "suffix"), [("post", "/approve"), ("delete", "")]
    )
    async def test_character_in_another_game_not_found(
        self, auth_as, client, db_session, game, gm, player, method, suffix
    ):
        other_game = await GameRepository(db_session, principal=gm).create(
            "Other Campaign",
            "dnd5e",
            ["dnd5e"],
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
        character = await _make_character(db_session, player)
        await _put_in_game(db_session, character, other_game.id)
        client = auth_as(gm)

        response = await getattr(client, method)(
            f"/games/{game.id}/characters/{character.id}{suffix}"
        )

        assert response.status_code == 404
