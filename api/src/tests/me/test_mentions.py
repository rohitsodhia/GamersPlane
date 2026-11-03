from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.configs import configs
from app.models import Event, EventRecipient, Post
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import (
    ActivatedUserFactory,
    ForumFactory,
    PostFactory,
    ThreadFactory,
)
from tests.factories.prose import mentioning_doc


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
        dismissed_at=None,
        post_state=Post.States.PUBLISHED,
        deleted=None,
        thread_deleted=None,
        thread=None,
    ):
        if thread is None:
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
        if thread.first_post_id is None:
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
            EventRecipient(
                event_id=event.id,
                user_id=user.id,
                read_at=read_at,
                dismissed_at=dismissed_at,
            )
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

        assert [m["eventId"] for m in body["items"]] == [newer.id, older.id]
        assert body["items"][0] == {
            "type": "mention",
            "eventId": newer.id,
            "actor": {"id": actor.id, "username": actor.username},
            "threadId": newer_post.thread_id,
            "threadTitle": "Newer",
            "postId": newer_post.id,
            "forumId": newer_post.thread.forum_id,
            "createdAt": "2026-02-01T00:00:00Z",
            "read": True,
        }
        assert body["items"][1]["read"] is False
        assert body["hasMore"] is False

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

        assert body["items"] == []
        assert body["count"] == 0

    async def test_a_scan_cut_short_by_the_cap_with_nothing_visible_ends_the_page(
        self, auth_as, create, make_mention, reader, monkeypatch
    ):
        monkeypatch.setattr("app.events.functions.MAX_NOTIFICATIONS_SCANNED", 2)
        await make_mention(reader)
        closed = await create(ForumFactory, heritage=[])
        for _ in range(3):
            await make_mention(reader, forum=closed)

        body = (
            await auth_as(reader).get("/me/notifications", params={"limit": 1})
        ).json()

        # The newest rows are hidden; the cap stops the scan before the visible one.
        assert body["items"] == []
        assert body["hasMore"] is False

    async def test_mentions_in_a_forum_the_user_cannot_read_are_hidden(
        self, auth_as, create, make_mention, reader
    ):
        closed = await create(ForumFactory, heritage=[])
        await make_mention(reader, forum=closed)
        visible, _ = await make_mention(reader)

        body = (await auth_as(reader).get("/me/notifications")).json()

        assert [m["eventId"] for m in body["items"]] == [visible.id]
        assert body["count"] == 1

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

        assert [m["eventId"] for m in body["items"]] == [
            event.id for event in reversed(visible)
        ]
        assert body["hasMore"] is False


class TestViewingAThreadDismisses:
    async def test_only_mentions_in_the_posts_that_loaded_are_dismissed(
        self, auth_as, create, make_mention, reader, db_session
    ):
        thread = await create(ThreadFactory)
        shown, shown_post = await make_mention(reader, thread=thread)
        other_page, _ = await make_mention(reader, thread=thread)
        shown_post.published_at = datetime.now(UTC)
        await db_session.flush()

        response = await auth_as(reader).post(
            f"/threads/{thread.id}/read",
            json={"post_id": shown_post.id, "post_ids": [shown_post.id]},
        )

        assert response.status_code == 204
        rows = {
            row.event_id: row
            for row in await db_session.scalars(select(EventRecipient))
        }
        assert rows[shown.id].dismissed_at is not None
        assert rows[shown.id].read_at is not None
        assert rows[other_page.id].dismissed_at is None

    async def test_more_ids_than_a_page_holds_is_rejected(
        self, auth_as, create, make_mention, reader
    ):
        thread = await create(ThreadFactory)
        _, post = await make_mention(reader, thread=thread)

        response = await auth_as(reader).post(
            f"/threads/{thread.id}/read",
            json={
                "post_id": post.id,
                "post_ids": list(range(1, configs.PAGINATE_PER_PAGE + 2)),
            },
        )

        assert response.status_code == 422
