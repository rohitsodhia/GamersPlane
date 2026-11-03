from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import Event, EventRecipient, Player, Post
from app.repositories import PlayerRepository
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import (
    ActivatedUserFactory,
    ForumFactory,
    PostFactory,
    ThreadFactory,
)
from tests.factories.prose import mentioning_doc
from tests.game_forum import make_game_forum


@pytest.fixture(autouse=True)
async def _open_site_root(wrap_in_savepoint, open_forums):
    await open_forums(SITE_ROOT_FORUM_ID)


@pytest.fixture
async def actor(create):
    return await create(ActivatedUserFactory)


@pytest.fixture
async def reader(create):
    return await create(ActivatedUserFactory)


@pytest.fixture
def make_mention(create, db_session, actor):
    """A thread whose first post (titled ``title``) mentions ``user``, with the
    event and ``user``'s row for it. Returns ``(event, post)``."""

    async def _make(
        user,
        *,
        title="Topic",
        forum=None,
        created_at=None,
        read_at=None,
        post_state=Post.States.PUBLISHED,
        deleted=None,
        thread_deleted=None,
    ):
        thread = await create(
            ThreadFactory,
            deleted=thread_deleted,
            **({"forum": forum} if forum else {}),
        )
        post = await create(
            PostFactory,
            thread=thread,
            author=actor,
            title=title,
            body=mentioning_doc(user.id),
            state=post_state,
            deleted=deleted,
        )
        thread.first_post_id = post.id
        event = Event(
            type=Event.Types.MENTION,
            actor_id=actor.id,
            post_id=post.id,
            thread_id=thread.id,
        )
        if created_at is not None:
            event.created_at = created_at
        db_session.add(event)
        await db_session.flush()
        db_session.add(
            EventRecipient(event_id=event.id, user_id=user.id, read_at=read_at)
        )
        await db_session.flush()
        return event, post

    return _make


class TestGetMentions:
    async def test_lists_mentions_newest_first_with_their_fields(
        self, auth_as, make_mention, reader, actor
    ):
        older, _ = await make_mention(
            reader, title="Older", created_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
        newer, newer_post = await make_mention(
            reader,
            title="Newer",
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
            read_at=datetime(2026, 2, 2, tzinfo=UTC),
        )

        body = (await auth_as(reader).get("/me/notifications")).json()

        assert [m["eventId"] for m in body["mentions"]] == [newer.id, older.id]
        assert body["mentions"][0] == {
            "eventId": newer.id,
            "actor": {"id": actor.id, "username": actor.username},
            "threadId": newer_post.thread_id,
            "threadTitle": "Newer",
            "postId": newer_post.id,
            "forumId": newer_post.thread.forum_id,
            "createdAt": "2026-02-01T00:00:00Z",
            "read": True,
        }
        assert body["mentions"][1]["read"] is False
        assert body["hasMoreMentions"] is False

    async def test_only_the_users_own_mentions_are_listed(
        self, auth_as, create, make_mention, reader
    ):
        other = await create(ActivatedUserFactory)
        await make_mention(other)

        body = (await auth_as(reader).get("/me/notifications")).json()

        assert body["mentions"] == []

    async def test_count_adds_unread_mentions_beyond_the_page_to_the_items(
        self, auth_as, create, make_mention, reader, db_session
    ):
        gf = await make_game_forum(create, db_session)
        await PlayerRepository(db_session, principal=reader).attach_player_to_game(
            gf.game.id, reader.id, is_gm=False, state=Player.States.INVITED
        )
        for _ in range(3):
            await make_mention(reader)
        await make_mention(reader, read_at=datetime(2026, 1, 1, tzinfo=UTC))

        body = (
            await auth_as(reader).get("/me/notifications", params={"limit": 1})
        ).json()

        assert len(body["mentions"]) == 1
        assert len(body["invites"]) == 1
        # One invite plus three unread mentions; the read one is left out.
        assert body["count"] == 4

    @pytest.mark.parametrize(
        "hidden",
        [
            {"deleted": datetime(2026, 1, 1, tzinfo=UTC)},
            {"thread_deleted": datetime(2026, 1, 1, tzinfo=UTC)},
            {"post_state": Post.States.DRAFT},
        ],
        ids=["post_deleted", "thread_deleted", "draft"],
    )
    async def test_mentions_of_a_post_that_is_gone_or_unpublished_are_hidden(
        self, auth_as, make_mention, reader, hidden
    ):
        await make_mention(reader, **hidden)

        body = (await auth_as(reader).get("/me/notifications")).json()

        assert body["mentions"] == []
        assert body["count"] == 0

    async def test_a_scan_cut_short_by_the_cap_still_offers_more(
        self, auth_as, create, make_mention, reader, monkeypatch
    ):
        monkeypatch.setattr("app.events.functions.MAX_MENTIONS_SCANNED", 2)
        await make_mention(reader)
        closed = await create(ForumFactory, heritage=[])
        for _ in range(3):
            await make_mention(reader, forum=closed)

        body = (
            await auth_as(reader).get("/me/notifications", params={"limit": 1})
        ).json()

        # The newest rows are hidden; the cap stops the scan before the visible one.
        assert body["mentions"] == []
        assert body["hasMoreMentions"] is False

    async def test_mentions_in_a_forum_the_user_cannot_read_are_hidden(
        self, auth_as, create, make_mention, reader
    ):
        closed = await create(ForumFactory, heritage=[])
        await make_mention(reader, forum=closed)
        visible, _ = await make_mention(reader)

        body = (await auth_as(reader).get("/me/notifications")).json()

        assert [m["eventId"] for m in body["mentions"]] == [visible.id]
        assert body["count"] == 1

    async def test_paging_by_limit_and_before(self, auth_as, make_mention, reader):
        events = [(await make_mention(reader))[0] for _ in range(5)]
        newest_first = [event.id for event in reversed(events)]
        client = auth_as(reader)

        first = (await client.get("/me/notifications", params={"limit": 2})).json()
        second = (
            await client.get(
                "/me/notifications",
                params={"limit": 2, "before": first["mentions"][-1]["eventId"]},
            )
        ).json()
        last = (
            await client.get(
                "/me/notifications",
                params={"limit": 2, "before": second["mentions"][-1]["eventId"]},
            )
        ).json()

        assert [m["eventId"] for m in first["mentions"]] == newest_first[:2]
        assert first["hasMoreMentions"] is True
        assert [m["eventId"] for m in second["mentions"]] == newest_first[2:4]
        assert second["hasMoreMentions"] is True
        assert [m["eventId"] for m in last["mentions"]] == newest_first[4:]
        assert last["hasMoreMentions"] is False

    async def test_a_page_skips_past_hidden_mentions_to_fill_itself(
        self, auth_as, create, make_mention, reader
    ):
        visible = [(await make_mention(reader))[0] for _ in range(2)]
        closed = await create(ForumFactory, heritage=[])
        for _ in range(3):
            await make_mention(reader, forum=closed)

        body = (
            await auth_as(reader).get("/me/notifications", params={"limit": 2})
        ).json()

        assert [m["eventId"] for m in body["mentions"]] == [
            event.id for event in reversed(visible)
        ]
        assert body["hasMoreMentions"] is False


class TestMarkRead:
    async def test_marks_the_callers_row_read(
        self, auth_as, make_mention, reader, db_session
    ):
        event, _ = await make_mention(reader)

        response = await auth_as(reader).post(
            f"/me/notifications/mentions/{event.id}/read"
        )

        assert response.status_code == 204
        row = await db_session.scalar(select(EventRecipient))
        assert row.read_at is not None

    async def test_someone_elses_event_is_a_404_and_stays_unread(
        self, auth_as, create, make_mention, reader, db_session
    ):
        event, _ = await make_mention(reader)
        stranger = await create(ActivatedUserFactory)

        response = await auth_as(stranger).post(
            f"/me/notifications/mentions/{event.id}/read"
        )

        assert response.status_code == 404
        assert (await db_session.scalar(select(EventRecipient))).read_at is None

    async def test_read_all_clears_the_count(self, auth_as, make_mention, reader):
        for _ in range(2):
            await make_mention(reader)
        client = auth_as(reader)

        response = await client.post("/me/notifications/mentions/read-all")
        body = (await client.get("/me/notifications")).json()

        assert response.status_code == 204
        assert body["count"] == 0
        assert [m["read"] for m in body["mentions"]] == [True, True]
