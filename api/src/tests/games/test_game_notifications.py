"""Stored notifications for game invites, applications, and character
submissions: when the routes raise them, and when the notifications list shows
them (the live state has to still match)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text

from app.models import Event, EventRecipient, Player
from app.repositories import GameRepository, PlayerRepository
from tests.factories import ActivatedUserFactory, ForumFactory, SystemFactory
from tests.games.test_routes import _make_character


@pytest.fixture(autouse=True)
async def games_root_forum(wrap_in_savepoint, create, db_session):
    forum = await create(ForumFactory, id=2, heritage=[])
    # An explicit id bypasses the forums sequence, so move it past that id.
    await db_session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('forums', 'id'), "
            "(SELECT MAX(id) FROM forums))"
        )
    )
    return forum


@pytest.fixture
async def system(create):
    return await create(SystemFactory, id="dnd5e")


@pytest.fixture
async def gm(create):
    return await create(ActivatedUserFactory)


@pytest.fixture
async def game(db_session, gm, system):
    return await GameRepository(db_session, principal=gm).create(
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


@pytest.fixture
def add_player(db_session, create, game, gm):
    async def _add(state=Player.States.ACCEPTED, is_gm=False):
        user = await create(ActivatedUserFactory)
        await PlayerRepository(db_session, principal=gm).attach_player_to_game(
            game.id, user.id, is_gm=is_gm, state=state
        )
        return user

    return _add


@pytest.fixture
def events(db_session):
    async def _events(type_):
        return list(await db_session.scalars(select(Event).where(Event.type == type_)))

    return _events


@pytest.fixture
def listed(auth_as):
    """The user's notifications as the API lists them."""

    async def _listed(user):
        return (await auth_as(user).get("/me/notifications")).json()

    return _listed


async def _event_count(db_session):
    return await db_session.scalar(select(func.count()).select_from(Event))


class TestInvite:
    async def test_notifies_the_invitee_with_the_gm_as_actor(
        self, auth_as, create, game, gm, listed
    ):
        invitee = await create(ActivatedUserFactory)

        response = await auth_as(gm).post(
            f"/games/{game.id}/invite", json={"username": invitee.username}
        )

        assert response.status_code == 204
        body = await listed(invitee)
        assert body["count"] == 1
        [item] = body["items"]
        assert item["type"] == "game_invite"
        assert item["actor"] == {"id": gm.id, "username": gm.username}
        assert item["gameId"] == game.id
        assert item["gameTitle"] == "My Campaign"
        assert item["read"] is False
        # Nobody else is told, the inviting GM included.
        assert (await listed(gm))["items"] == []

    async def test_a_banned_invitee_is_not_notified(
        self, auth_as, create, db_session, game, gm
    ):
        invitee = await create(ActivatedUserFactory)
        invitee.banned = datetime.now(UTC)
        await db_session.flush()

        response = await auth_as(gm).post(
            f"/games/{game.id}/invite", json={"username": invitee.username}
        )

        assert response.status_code == 204
        assert await _event_count(db_session) == 0

    async def test_inviting_again_after_a_decline_reuses_and_raises_the_event(
        self, auth_as, create, db_session, game, gm, add_player, listed, events
    ):
        co_gm = await add_player(is_gm=True)
        invitee = await create(ActivatedUserFactory)
        await auth_as(gm).post(
            f"/games/{game.id}/invite", json={"username": invitee.username}
        )
        [first] = (await listed(invitee))["items"]
        await auth_as(invitee).post(f"/me/notifications/{first['eventId']}/dismiss")
        await auth_as(invitee).delete(f"/games/{game.id}/player/{invitee.id}")
        [event] = await events(Event.Types.GAME_INVITE)
        old_created_at = event.created_at

        await auth_as(co_gm).post(
            f"/games/{game.id}/invite", json={"username": invitee.username}
        )

        assert await _event_count(db_session) == 1
        await db_session.refresh(event)
        assert event.actor_id == co_gm.id
        assert event.created_at > old_created_at
        [again] = (await listed(invitee))["items"]
        assert again["eventId"] == first["eventId"]
        assert again["read"] is False
        assert again["actor"]["id"] == co_gm.id

    async def test_two_invitees_get_separate_events(
        self, auth_as, create, game, gm, listed
    ):
        first = await create(ActivatedUserFactory)
        second = await create(ActivatedUserFactory)
        for invitee in (first, second):
            await auth_as(gm).post(
                f"/games/{game.id}/invite", json={"username": invitee.username}
            )

        [first_item] = (await listed(first))["items"]
        [second_item] = (await listed(second))["items"]
        assert first_item["eventId"] != second_item["eventId"]

        await auth_as(first).post(f"/me/notifications/{first_item['eventId']}/dismiss")
        assert (await listed(first))["items"] == []
        assert [i["eventId"] for i in (await listed(second))["items"]] == [
            second_item["eventId"]
        ]


class TestApplication:
    async def test_notifies_every_accepted_gm_but_nobody_else(
        self, auth_as, create, db_session, game, gm, add_player, listed, events
    ):
        co_gm = await add_player(is_gm=True)
        invited_gm = await add_player(state=Player.States.INVITED, is_gm=True)
        member = await add_player()
        applicant = await create(ActivatedUserFactory)

        response = await auth_as(applicant).post(f"/games/{game.id}/apply")

        assert response.status_code == 204
        for gm_user in (gm, co_gm):
            [item] = (await listed(gm_user))["items"]
            assert item["type"] == "game_application"
            assert item["actor"] == {
                "id": applicant.id,
                "username": applicant.username,
            }
            assert (item["gameId"], item["gameTitle"]) == (game.id, "My Campaign")
        for other in (invited_gm, member, applicant):
            assert (await listed(other))["items"] == []
        applications = await events(Event.Types.GAME_APPLICATION)
        recipient_ids = set(
            await db_session.scalars(
                select(EventRecipient.user_id).where(
                    EventRecipient.event_id.in_([e.id for e in applications])
                )
            )
        )
        assert recipient_ids == {gm.id, co_gm.id}

    async def test_two_applicants_give_the_gm_separate_events(
        self, auth_as, create, game, gm, listed
    ):
        for _ in range(2):
            await auth_as(await create(ActivatedUserFactory)).post(
                f"/games/{game.id}/apply"
            )

        body = await listed(gm)

        assert body["count"] == 2
        assert len({i["eventId"] for i in body["items"]}) == 2
        assert len({i["actor"]["id"] for i in body["items"]}) == 2

    async def test_a_banned_gm_is_skipped(
        self, auth_as, create, db_session, game, gm, add_player, events
    ):
        co_gm = await add_player(is_gm=True)
        co_gm.banned = datetime.now(UTC)
        await db_session.flush()
        applicant = await create(ActivatedUserFactory)

        await auth_as(applicant).post(f"/games/{game.id}/apply")

        [application] = await events(Event.Types.GAME_APPLICATION)
        recipient_ids = set(
            await db_session.scalars(
                select(EventRecipient.user_id).where(
                    EventRecipient.event_id == application.id
                )
            )
        )
        assert recipient_ids == {gm.id}

    async def test_a_rejected_application_raises_nothing(
        self, auth_as, create, db_session, game, gm
    ):
        game.public = False
        await db_session.flush()
        applicant = await create(ActivatedUserFactory)

        response = await auth_as(applicant).post(f"/games/{game.id}/apply")

        assert response.status_code == 403
        assert await _event_count(db_session) == 0

    async def test_applying_again_reuses_the_event_and_reaches_the_new_gm(
        self, auth_as, create, db_session, game, gm, add_player, listed, events
    ):
        applicant = await create(ActivatedUserFactory)
        await auth_as(applicant).post(f"/games/{game.id}/apply")
        [first] = (await listed(gm))["items"]
        await auth_as(gm).post(f"/me/notifications/{first['eventId']}/dismiss")
        await auth_as(applicant).delete(f"/games/{game.id}/player/{applicant.id}")
        co_gm = await add_player(is_gm=True)
        [event] = await events(Event.Types.GAME_APPLICATION)
        old_created_at = event.created_at

        await auth_as(applicant).post(f"/games/{game.id}/apply")

        assert await _event_count(db_session) == 1
        await db_session.refresh(event)
        assert event.created_at > old_created_at
        for gm_user in (gm, co_gm):
            [item] = (await listed(gm_user))["items"]
            assert item["eventId"] == first["eventId"]
            assert item["read"] is False


class TestCharacterSubmitted:
    @pytest.fixture
    async def character(self, db_session, add_player):
        player = await add_player()
        return player, await _make_character(db_session, player, name="Strider")

    async def test_notifies_the_gms_with_the_character_and_owner(
        self, auth_as, game, gm, character, listed
    ):
        player, strider = character

        response = await auth_as(player).post(
            f"/games/{game.id}/characters", json={"character_id": strider.id}
        )

        assert response.status_code == 204
        [item] = (await listed(gm))["items"]
        assert item["type"] == "character_submitted"
        assert item["actor"] == {"id": player.id, "username": player.username}
        assert item["gameId"] == game.id
        assert item["gameTitle"] == "My Campaign"
        assert item["characterId"] == strider.id
        assert item["characterName"] == "Strider"
        assert (await listed(player))["items"] == []

    async def test_a_gm_submitting_their_own_character_raises_nothing(
        self, auth_as, db_session, game, add_player
    ):
        co_gm = await add_player(is_gm=True)
        own = await _make_character(db_session, co_gm)

        response = await auth_as(co_gm).post(
            f"/games/{game.id}/characters", json={"character_id": own.id}
        )

        assert response.status_code == 204
        assert await _event_count(db_session) == 0

    async def test_a_rejected_submission_raises_nothing(
        self, auth_as, db_session, game, character
    ):
        player, strider = character
        strider.game_id = game.id
        await db_session.flush()

        response = await auth_as(player).post(
            f"/games/{game.id}/characters", json={"character_id": strider.id}
        )

        assert response.status_code == 409
        assert await _event_count(db_session) == 0

    async def test_submitting_again_after_a_withdrawal_reuses_the_event(
        self, auth_as, db_session, game, gm, character, listed
    ):
        player, strider = character
        client = auth_as(player)
        await client.post(
            f"/games/{game.id}/characters", json={"character_id": strider.id}
        )
        [first] = (await listed(gm))["items"]
        await auth_as(gm).post(f"/me/notifications/{first['eventId']}/dismiss")
        await auth_as(player).delete(f"/games/{game.id}/characters/{strider.id}")

        await auth_as(player).post(
            f"/games/{game.id}/characters", json={"character_id": strider.id}
        )

        assert await _event_count(db_session) == 1
        [again] = (await listed(gm))["items"]
        assert again["eventId"] == first["eventId"]
        assert again["read"] is False


class TestResolution:
    """Nothing is deleted when the thing is dealt with; the item just stops
    showing once the live state no longer matches."""

    async def test_an_invite_goes_when_accepted_or_declined(
        self, auth_as, create, game, gm, listed
    ):
        accepter = await create(ActivatedUserFactory)
        decliner = await create(ActivatedUserFactory)
        for invitee in (accepter, decliner):
            await auth_as(gm).post(
                f"/games/{game.id}/invite", json={"username": invitee.username}
            )

        await auth_as(accepter).post(f"/games/{game.id}/accept_invite")
        await auth_as(decliner).delete(f"/games/{game.id}/player/{decliner.id}")

        for invitee in (accepter, decliner):
            body = await listed(invitee)
            assert body["items"] == []
            assert body["count"] == 0

    async def test_an_application_goes_when_approved(
        self, auth_as, create, game, gm, listed
    ):
        applicant = await create(ActivatedUserFactory)
        await auth_as(applicant).post(f"/games/{game.id}/apply")

        await auth_as(gm).post(f"/games/{game.id}/player/{applicant.id}/approve")

        body = await listed(gm)
        assert body["items"] == []
        assert body["count"] == 0

    async def test_an_application_goes_when_withdrawn_or_declined(
        self, auth_as, create, game, gm, listed
    ):
        withdrawer = await create(ActivatedUserFactory)
        declined = await create(ActivatedUserFactory)
        await auth_as(withdrawer).post(f"/games/{game.id}/apply")
        await auth_as(declined).post(f"/games/{game.id}/apply")

        await auth_as(withdrawer).delete(f"/games/{game.id}/player/{withdrawer.id}")
        await auth_as(gm).delete(f"/games/{game.id}/player/{declined.id}")

        assert (await listed(gm))["items"] == []

    async def test_an_application_goes_for_a_gm_who_is_no_longer_one(
        self, auth_as, create, game, gm, add_player, listed
    ):
        co_gm = await add_player(is_gm=True)
        await auth_as(await create(ActivatedUserFactory)).post(
            f"/games/{game.id}/apply"
        )
        assert len((await listed(co_gm))["items"]) == 1

        await auth_as(gm).post(f"/games/{game.id}/player/{co_gm.id}/toggle_gm")

        body = await listed(co_gm)
        assert body["items"] == []
        assert body["count"] == 0
        assert len((await listed(gm))["items"]) == 1

    async def test_a_character_goes_when_approved_or_removed(
        self, auth_as, db_session, game, gm, add_player, listed
    ):
        player = await add_player()
        approved = await _make_character(db_session, player, name="Approved")
        rejected = await _make_character(db_session, player, name="Rejected")
        player_client = auth_as(player)
        for character in (approved, rejected):
            await player_client.post(
                f"/games/{game.id}/characters", json={"character_id": character.id}
            )
        assert len((await listed(gm))["items"]) == 2

        await auth_as(gm).post(f"/games/{game.id}/characters/{approved.id}/approve")
        await auth_as(gm).delete(f"/games/{game.id}/characters/{rejected.id}")

        assert (await listed(gm))["items"] == []

    async def test_a_character_goes_when_deleted_or_moved_to_another_game(
        self, auth_as, db_session, game, gm, add_player, listed
    ):
        player = await add_player()
        deleted = await _make_character(db_session, player, name="Deleted")
        moved = await _make_character(db_session, player, name="Moved")
        for character in (deleted, moved):
            await auth_as(player).post(
                f"/games/{game.id}/characters", json={"character_id": character.id}
            )

        deleted.deleted = datetime.now(UTC)
        moved.game_id = None
        await db_session.flush()

        assert (await listed(gm))["items"] == []

    async def test_a_character_goes_when_the_game_is_deleted(
        self, auth_as, db_session, game, gm, add_player, listed
    ):
        player = await add_player()
        strider = await _make_character(db_session, player)
        await auth_as(player).post(
            f"/games/{game.id}/characters", json={"character_id": strider.id}
        )

        game.deleted = datetime.now(UTC)
        await db_session.flush()

        assert (await listed(gm))["items"] == []

    async def test_everything_goes_when_the_game_is_retired(
        self, auth_as, create, db_session, game, gm, add_player, listed
    ):
        invitee = await create(ActivatedUserFactory)
        await auth_as(gm).post(
            f"/games/{game.id}/invite", json={"username": invitee.username}
        )
        await auth_as(await create(ActivatedUserFactory)).post(
            f"/games/{game.id}/apply"
        )
        player = await add_player()
        strider = await _make_character(db_session, player)
        await auth_as(player).post(
            f"/games/{game.id}/characters", json={"character_id": strider.id}
        )
        assert (await listed(gm))["count"] == 2

        await GameRepository(db_session, principal=gm).toggle_retire(game)

        assert (await listed(gm)) == {
            "items": [],
            "hasMore": False,
            "nextCursor": None,
            "count": 0,
        }
        assert (await listed(invitee))["items"] == []
