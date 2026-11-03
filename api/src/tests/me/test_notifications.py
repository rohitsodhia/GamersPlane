import pytest

from app.models import Player
from app.repositories import GameRepository, PlayerRepository
from tests.factories import ActivatedUserFactory
from tests.game_forum import make_character, make_game_forum


@pytest.fixture
async def gf(create, db_session):
    return await make_game_forum(create, db_session)


async def _attach(db_session, game, user, state, is_gm=False):
    await PlayerRepository(db_session, principal=user).attach_player_to_game(
        game.id, user.id, is_gm=is_gm, state=state
    )


class TestGetNotifications:
    async def test_gm_sees_pending_players_and_characters(
        self, auth_as, create, db_session, gf
    ):
        for _ in range(2):
            applicant = await create(ActivatedUserFactory)
            await _attach(db_session, gf.game, applicant, Player.States.APPLIED)
        member = await create(ActivatedUserFactory)
        await _attach(db_session, gf.game, member, Player.States.ACCEPTED)
        await make_character(db_session, member, gf.game, approved=False)
        # Already approved, soft-deleted, and unsubmitted characters don't count.
        await make_character(db_session, member, gf.game)
        await make_character(
            db_session, member, gf.game, approved=False, deleted=gf.game.created
        )
        await make_character(db_session, member, game=None)
        client = auth_as(gf.gm)

        body = (await client.get("/me/notifications")).json()

        assert body["pending"] == [
            {
                "gameId": gf.game.id,
                "title": gf.game.title,
                "players": 2,
                "characters": 1,
            }
        ]
        assert body["invites"] == []
        assert body["count"] == 1

    async def test_characters_only_game_is_listed(
        self, auth_as, create, db_session, gf
    ):
        member = await create(ActivatedUserFactory)
        await _attach(db_session, gf.game, member, Player.States.ACCEPTED)
        await make_character(db_session, member, gf.game, approved=False)
        client = auth_as(gf.gm)

        body = (await client.get("/me/notifications")).json()

        assert [(i["players"], i["characters"]) for i in body["pending"]] == [(0, 1)]

    async def test_gm_who_has_not_accepted_sees_no_pending_but_keeps_the_invite(
        self, auth_as, create, db_session, gf
    ):
        applicant = await create(ActivatedUserFactory)
        await _attach(db_session, gf.game, applicant, Player.States.APPLIED)
        invited_gm = await create(ActivatedUserFactory)
        await _attach(db_session, gf.game, invited_gm, Player.States.INVITED, True)
        client = auth_as(invited_gm)

        body = (await client.get("/me/notifications")).json()

        assert body["pending"] == []
        assert [i["gameId"] for i in body["invites"]] == [gf.game.id]

    async def test_game_with_nothing_pending_is_absent(
        self, auth_as, create, db_session, gf
    ):
        # Only the second game has anything waiting.
        second = await gf.make_game("Second")
        await _attach(db_session, second.game, gf.gm, Player.States.ACCEPTED, True)
        applicant = await create(ActivatedUserFactory)
        await _attach(db_session, second.game, applicant, Player.States.APPLIED)
        client = auth_as(gf.gm)

        body = (await client.get("/me/notifications")).json()

        assert [item["gameId"] for item in body["pending"]] == [second.game.id]

    async def test_non_gm_players_dont_see_pending_for_the_game(
        self, auth_as, create, db_session, gf
    ):
        member = await create(ActivatedUserFactory)
        await _attach(db_session, gf.game, member, Player.States.ACCEPTED)
        applicant = await create(ActivatedUserFactory)
        await _attach(db_session, gf.game, applicant, Player.States.APPLIED)
        client = auth_as(member)

        body = (await client.get("/me/notifications")).json()

        assert body == {"pending": [], "invites": [], "count": 0}

    async def test_retired_game_is_excluded(self, auth_as, create, db_session, gf):
        applicant = await create(ActivatedUserFactory)
        await _attach(db_session, gf.game, applicant, Player.States.APPLIED)
        invitee = await create(ActivatedUserFactory)
        await _attach(db_session, gf.game, invitee, Player.States.INVITED)
        await GameRepository(db_session, principal=gf.gm).toggle_retire(gf.game)

        gm_body = (await auth_as(gf.gm).get("/me/notifications")).json()
        invitee_body = (await auth_as(invitee).get("/me/notifications")).json()

        assert gm_body["count"] == 0
        assert invitee_body["count"] == 0

    async def test_invite_shows_for_the_invited_user_only(
        self, auth_as, create, db_session, gf
    ):
        invitee = await create(ActivatedUserFactory)
        await _attach(db_session, gf.game, invitee, Player.States.INVITED)

        invitee_body = (await auth_as(invitee).get("/me/notifications")).json()
        gm_body = (await auth_as(gf.gm).get("/me/notifications")).json()

        assert invitee_body["invites"] == [
            {"gameId": gf.game.id, "title": gf.game.title}
        ]
        assert invitee_body["pending"] == []
        assert gm_body["invites"] == []

    async def test_items_are_ordered_by_title(self, auth_as, create, db_session, gf):
        # Created out of order on purpose: the API order is the title order.
        for title in ("Charlie", "Alpha", "Bravo"):
            pending_game = await gf.make_game(title)
            await _attach(
                db_session, pending_game.game, gf.gm, Player.States.ACCEPTED, True
            )
            applicant = await create(ActivatedUserFactory)
            await _attach(
                db_session, pending_game.game, applicant, Player.States.APPLIED
            )
        for title in ("Zulu", "Yankee"):
            invite_game = await gf.make_game(title)
            await _attach(db_session, invite_game.game, gf.gm, Player.States.INVITED)
        client = auth_as(gf.gm)

        body = (await client.get("/me/notifications")).json()

        assert [i["title"] for i in body["pending"]] == ["Alpha", "Bravo", "Charlie"]
        assert [i["title"] for i in body["invites"]] == ["Yankee", "Zulu"]

    async def test_count_is_pending_games_plus_invites(
        self, auth_as, create, db_session, gf
    ):
        # The user runs one game with an applicant and is invited to another.
        applicant = await create(ActivatedUserFactory)
        await _attach(db_session, gf.game, applicant, Player.States.APPLIED)
        other = await gf.make_game("Other")
        await _attach(db_session, other.game, gf.gm, Player.States.INVITED)
        client = auth_as(gf.gm)

        body = (await client.get("/me/notifications")).json()

        assert len(body["pending"]) == 1
        assert len(body["invites"]) == 1
        assert body["count"] == 2
