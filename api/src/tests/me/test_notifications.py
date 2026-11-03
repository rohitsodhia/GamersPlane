"""The notifications list across event types: one date-sorted list, its paging and
count, and read/dismiss. Mention visibility rules are in test_mentions.py, and the
rules for each game event type in tests/games/test_game_notifications.py."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import Event, EventRecipient, Player, User
from app.repositories import PlayerRepository
from tests.factories import ActivatedUserFactory
from tests.game_forum import make_character, make_game_forum


@pytest.fixture
async def gf(create, db_session):
    return await make_game_forum(create, db_session)


@pytest.fixture
async def other(create):
    return await create(ActivatedUserFactory)


@pytest.fixture
def make_event(db_session):
    """An event with a row for ``recipient``; ``created_at`` and the recipient's
    ``read_at``/``dismissed_at`` can be set."""

    async def _make(
        type_,
        actor,
        recipient,
        *,
        created_at,
        read_at=None,
        dismissed_at=None,
        **columns,
    ):
        event = Event(type=type_, actor_id=actor.id, created_at=created_at, **columns)
        db_session.add(event)
        await db_session.flush()
        db_session.add(
            EventRecipient(
                event_id=event.id,
                user_id=recipient.id,
                read_at=read_at,
                dismissed_at=dismissed_at,
            )
        )
        await db_session.flush()
        return event

    return _make


@pytest.fixture
def make_invite(db_session, make_event, gf):
    """An invite of ``invitee`` (who gets an INVITED player row) to the game."""

    async def _make(invitee, **kwargs):
        await PlayerRepository(db_session, principal=invitee).attach_player_to_game(
            gf.game.id, invitee.id, state=Player.States.INVITED
        )
        return await make_event(
            Event.Types.GAME_INVITE,
            gf.gm,
            invitee,
            game_id=gf.game.id,
            subject_user_id=invitee.id,
            **kwargs,
        )

    return _make


@pytest.fixture
def make_application(create, db_session, make_event, gf):
    """An application to the game by a new user, notifying the GM."""

    async def _make(**kwargs):
        applicant = await create(ActivatedUserFactory)
        await PlayerRepository(db_session, principal=applicant).attach_player_to_game(
            gf.game.id, applicant.id, state=Player.States.APPLIED
        )
        return await make_event(
            Event.Types.GAME_APPLICATION,
            applicant,
            gf.gm,
            game_id=gf.game.id,
            subject_user_id=applicant.id,
            **kwargs,
        )

    return _make


def _at(month):
    return datetime(2026, month, 1, tzinfo=UTC)


class TestGetNotifications:
    async def test_every_type_is_one_list_newest_first(
        self, auth_as, create, db_session, gf, make_event, make_application
    ):
        application = await make_application(created_at=_at(3))
        submitter = await create(ActivatedUserFactory)
        character = await make_character(db_session, submitter, gf.game, approved=False)
        submitted = await make_event(
            Event.Types.CHARACTER_SUBMITTED,
            submitter,
            gf.gm,
            created_at=_at(2),
            game_id=gf.game.id,
            character_id=character.id,
        )
        second = await gf.make_game("Second")
        await PlayerRepository(db_session, principal=gf.gm).attach_player_to_game(
            second.game.id, gf.gm.id, state=Player.States.INVITED
        )
        invite = await make_event(
            Event.Types.GAME_INVITE,
            second.gm,
            gf.gm,
            created_at=_at(1),
            game_id=second.game.id,
            subject_user_id=gf.gm.id,
        )

        body = (await auth_as(gf.gm).get("/me/notifications")).json()

        assert body["count"] == 3
        assert body["hasMore"] is False
        assert body["nextCursor"] is None
        assert [(i["type"], i["eventId"]) for i in body["items"]] == [
            ("game_application", application.id),
            ("character_submitted", submitted.id),
            ("game_invite", invite.id),
        ]
        applicant = await db_session.get(User, application.actor_id)
        assert body["items"][0] == {
            "type": "game_application",
            "eventId": application.id,
            "actor": {"id": applicant.id, "username": applicant.username},
            "createdAt": "2026-03-01T00:00:00Z",
            "read": False,
            "gameId": gf.game.id,
            "gameTitle": gf.game.title,
        }
        assert body["items"][1]["characterName"] == character.name
        assert body["items"][2]["gameId"] == second.game.id

    async def test_only_the_users_own_rows_are_listed(
        self, auth_as, gf, other, make_invite
    ):
        await make_invite(other, created_at=_at(1))

        body = (await auth_as(gf.gm).get("/me/notifications")).json()

        assert body == {"items": [], "hasMore": False, "nextCursor": None, "count": 0}

    async def test_paging_follows_the_cursor_across_ties(
        self, auth_as, gf, make_application
    ):
        # The last two share a date, so the event id breaks the tie.
        events = [
            await make_application(created_at=_at(month)) for month in (2, 3, 4, 1, 1)
        ]
        client = auth_as(gf.gm)

        pages = []
        before = None
        while True:
            params = {"limit": 2, **({"before": before} if before else {})}
            body = (await client.get("/me/notifications", params=params)).json()
            pages.append(body)
            before = body["nextCursor"]
            if not body["hasMore"]:
                break

        newest_first = [events[i].id for i in (2, 1, 0, 4, 3)]
        assert [i["eventId"] for p in pages for i in p["items"]] == newest_first
        assert [p["hasMore"] for p in pages] == [True, True, False]
        assert pages[-1]["nextCursor"] is None

    async def test_a_raised_event_jumps_ahead_and_paging_stays_consistent(
        self, auth_as, db_session, gf, make_application
    ):
        # A reused event keeps its (low) id but gets a new date; the cursor is the
        # (date, id) pair, so paging still visits both exactly once.
        first = await make_application(created_at=_at(1))
        second = await make_application(created_at=_at(2))
        first.created_at = _at(3)
        await db_session.flush()
        client = auth_as(gf.gm)

        page_one = (await client.get("/me/notifications", params={"limit": 1})).json()
        page_two = (
            await client.get(
                "/me/notifications",
                params={"limit": 1, "before": page_one["nextCursor"]},
            )
        ).json()

        assert [i["eventId"] for i in page_one["items"]] == [first.id]
        assert [i["eventId"] for i in page_two["items"]] == [second.id]
        assert page_two["hasMore"] is False

    @pytest.mark.parametrize(
        "cursor",
        [
            "nonsense",
            "a_b",
            "1_2_3",
            "99999999999999999999999_1",
            "1_99999999999999999999",
        ],
        ids=[
            "no_separator",
            "non_numeric",
            "extra_part",
            "date_out_of_range",
            "event_id_out_of_range",
        ],
    )
    async def test_a_malformed_cursor_is_rejected(self, auth_as, gf, cursor):
        response = await auth_as(gf.gm).get(
            "/me/notifications", params={"before": cursor}
        )

        assert response.status_code == 400

    async def test_a_page_ending_exactly_at_the_end_has_no_more(
        self, auth_as, gf, make_application
    ):
        for month in (1, 2):
            await make_application(created_at=_at(month))

        body = (
            await auth_as(gf.gm).get("/me/notifications", params={"limit": 2})
        ).json()

        assert len(body["items"]) == 2
        assert body["hasMore"] is False
        assert body["nextCursor"] is None

    async def test_a_cursor_from_a_since_dismissed_event_still_pages(
        self, auth_as, gf, make_application
    ):
        newest = await make_application(created_at=_at(3))
        middle = await make_application(created_at=_at(2))
        oldest = await make_application(created_at=_at(1))
        client = auth_as(gf.gm)
        page_one = (await client.get("/me/notifications", params={"limit": 2})).json()
        assert [i["eventId"] for i in page_one["items"]] == [newest.id, middle.id]
        await client.post(f"/me/notifications/{middle.id}/dismiss")

        page_two = (
            await client.get(
                "/me/notifications", params={"before": page_one["nextCursor"]}
            )
        ).json()

        assert [i["eventId"] for i in page_two["items"]] == [oldest.id]

    async def test_count_covers_every_unread_item_beyond_the_page(
        self, auth_as, gf, make_application
    ):
        for month in (1, 2, 3):
            await make_application(created_at=_at(month))
        await make_application(created_at=_at(4), read_at=_at(5))

        body = (
            await auth_as(gf.gm).get("/me/notifications", params={"limit": 1})
        ).json()

        assert len(body["items"]) == 1
        assert body["count"] == 3


class TestReadAndDismiss:
    async def test_reading_a_game_event_marks_the_callers_row_read(
        self, auth_as, db_session, other, make_invite
    ):
        event = await make_invite(other, created_at=_at(1))

        response = await auth_as(other).post(f"/me/notifications/{event.id}/read")

        assert response.status_code == 204
        row = await db_session.get(EventRecipient, (event.id, other.id))
        assert row.read_at is not None
        body = (await auth_as(other).get("/me/notifications")).json()
        assert body["count"] == 0
        assert body["items"][0]["read"] is True

    async def test_dismissing_a_game_event_hides_it_and_reads_it(
        self, auth_as, db_session, gf, make_application
    ):
        dismissed = await make_application(created_at=_at(1))
        kept = await make_application(created_at=_at(2))
        client = auth_as(gf.gm)

        response = await client.post(f"/me/notifications/{dismissed.id}/dismiss")

        assert response.status_code == 204
        row = await db_session.get(EventRecipient, (dismissed.id, gf.gm.id))
        assert row.read_at is not None
        assert row.dismissed_at is not None
        body = (await client.get("/me/notifications")).json()
        assert [i["eventId"] for i in body["items"]] == [kept.id]
        assert body["count"] == 1

    async def test_read_all_route_reads_the_callers_rows(
        self, auth_as, gf, make_application
    ):
        await make_application(created_at=_at(1))
        await make_application(created_at=_at(2))
        client = auth_as(gf.gm)

        response = await client.post("/me/notifications/read-all")

        assert response.status_code == 204
        body = (await client.get("/me/notifications")).json()
        assert body["count"] == 0
        assert all(item["read"] for item in body["items"])

    async def test_someone_elses_event_is_a_404_and_unchanged(
        self, auth_as, db_session, gf, other, make_invite
    ):
        event = await make_invite(other, created_at=_at(1))

        for action in ("read", "dismiss"):
            response = await auth_as(gf.gm).post(
                f"/me/notifications/{event.id}/{action}"
            )
            assert response.status_code == 404
        row = await db_session.scalar(select(EventRecipient))
        assert (row.read_at, row.dismissed_at) == (None, None)
