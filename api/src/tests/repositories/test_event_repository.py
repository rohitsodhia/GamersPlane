from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import Event, EventRecipient, Post
from app.repositories import EventRepository
from tests.factories import ActivatedUserFactory, PostFactory, ThreadFactory


@pytest.fixture
async def event(create, db_session):
    post = await create(PostFactory)
    event = Event(
        type=Event.Types.MENTION,
        actor_id=post.author_id,
        post_id=post.id,
        thread_id=post.thread_id,
    )
    db_session.add(event)
    await db_session.flush()
    return event


class TestAddRecipients:
    async def test_a_user_who_already_has_a_row_keeps_their_read_time(
        self, create, db_session, event
    ):
        user = await create(ActivatedUserFactory)
        newcomer = await create(ActivatedUserFactory)
        read_at = datetime(2026, 1, 1, tzinfo=UTC)
        db_session.add(
            EventRecipient(event_id=event.id, user_id=user.id, read_at=read_at)
        )
        await db_session.flush()

        await EventRepository(db_session).add_recipients(
            event.id, {user.id, newcomer.id}
        )

        rows = (
            await db_session.execute(
                select(EventRecipient.user_id, EventRecipient.read_at)
            )
        ).all()
        assert dict(rows) == {user.id: read_at, newcomer.id: None}


class TestMarkRead:
    async def test_marking_again_keeps_the_first_read_time(
        self, create, db_session, event
    ):
        user = await create(ActivatedUserFactory)
        first = datetime(2026, 1, 1, tzinfo=UTC)
        db_session.add(EventRecipient(event_id=event.id, user_id=user.id))
        await db_session.flush()
        repo = EventRepository(db_session)
        assert await repo.mark_read(user.id, event.id) is True
        row = await db_session.get(EventRecipient, (event.id, user.id))
        row.read_at = first
        await db_session.flush()

        assert await repo.mark_read(user.id, event.id) is True

        assert row.read_at == first

    async def test_a_user_without_a_row_is_reported_and_nothing_changes(
        self, create, db_session, event
    ):
        owner = await create(ActivatedUserFactory)
        stranger = await create(ActivatedUserFactory)
        db_session.add(EventRecipient(event_id=event.id, user_id=owner.id))
        await db_session.flush()

        assert (
            await EventRepository(db_session).mark_read(stranger.id, event.id) is False
        )

        row = await db_session.get(EventRecipient, (event.id, owner.id))
        assert row.read_at is None


class TestDismiss:
    async def test_dismissing_sets_both_times_and_keeps_an_earlier_read_time(
        self, create, db_session, event
    ):
        user = await create(ActivatedUserFactory)
        unread = await create(ActivatedUserFactory)
        read_at = datetime(2026, 1, 1, tzinfo=UTC)
        db_session.add_all(
            [
                EventRecipient(event_id=event.id, user_id=user.id, read_at=read_at),
                EventRecipient(event_id=event.id, user_id=unread.id),
            ]
        )
        await db_session.flush()
        repo = EventRepository(db_session)

        assert await repo.dismiss(user.id, event.id) is True
        assert await repo.dismiss(unread.id, event.id) is True

        kept = await db_session.get(EventRecipient, (event.id, user.id))
        fresh = await db_session.get(EventRecipient, (event.id, unread.id))
        assert kept.read_at == read_at
        assert kept.dismissed_at is not None
        assert fresh.read_at is not None
        assert fresh.dismissed_at == fresh.read_at

    async def test_dismissing_again_keeps_the_first_dismissal(
        self, create, db_session, event
    ):
        user = await create(ActivatedUserFactory)
        first = datetime(2026, 1, 1, tzinfo=UTC)
        db_session.add(
            EventRecipient(
                event_id=event.id, user_id=user.id, read_at=first, dismissed_at=first
            )
        )
        await db_session.flush()

        assert await EventRepository(db_session).dismiss(user.id, event.id) is True

        row = await db_session.get(EventRecipient, (event.id, user.id))
        assert row.dismissed_at == first

    async def test_a_user_without_a_row_is_reported(self, create, event, db_session):
        stranger = await create(ActivatedUserFactory)

        assert await EventRepository(db_session).dismiss(stranger.id, event.id) is False


class TestDismissForPosts:
    async def test_only_the_users_rows_for_published_posts_of_the_thread(
        self, create, db_session
    ):
        user = await create(ActivatedUserFactory)
        other = await create(ActivatedUserFactory)
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread)
        draft = await create(PostFactory, thread=thread, state=Post.States.DRAFT)
        elsewhere = await create(PostFactory)
        unlisted = await create(PostFactory, thread=thread)
        events = {}
        for name, target in {
            "post": post,
            "draft": draft,
            "elsewhere": elsewhere,
            "unlisted": unlisted,
        }.items():
            events[name] = Event(
                type=Event.Types.MENTION,
                actor_id=target.author_id,
                post_id=target.id,
                thread_id=target.thread_id,
            )
            db_session.add(events[name])
        await db_session.flush()
        db_session.add_all(
            [EventRecipient(event_id=e.id, user_id=user.id) for e in events.values()]
            + [EventRecipient(event_id=events["post"].id, user_id=other.id)]
        )
        await db_session.flush()

        changed = await EventRepository(db_session).dismiss_for_posts(
            user.id, thread.id, [post.id, draft.id, elsewhere.id]
        )

        assert changed == 1
        rows = {
            (row.event_id, row.user_id): row
            for row in await db_session.scalars(select(EventRecipient))
        }
        dismissed = rows[(events["post"].id, user.id)]
        assert dismissed.dismissed_at is not None
        assert dismissed.read_at is not None
        own = {e.id for e in events.values()}
        assert [
            key
            for key, row in rows.items()
            if key[0] in own
            and row.dismissed_at is not None
            and key != (events["post"].id, user.id)
        ] == []

    async def test_an_empty_list_changes_nothing(self, create, db_session, event):
        user = await create(ActivatedUserFactory)
        db_session.add(EventRecipient(event_id=event.id, user_id=user.id))
        await db_session.flush()

        changed = await EventRepository(db_session).dismiss_for_posts(
            user.id, event.thread_id, []
        )

        assert changed == 0


class TestMarkAllRead:
    async def test_only_the_users_unread_rows_are_touched(
        self, create, db_session, event
    ):
        user = await create(ActivatedUserFactory)
        other = await create(ActivatedUserFactory)
        post = await create(PostFactory)
        second = Event(
            type=Event.Types.MENTION,
            actor_id=post.author_id,
            post_id=post.id,
            thread_id=post.thread_id,
        )
        db_session.add(second)
        await db_session.flush()
        earlier = datetime(2026, 1, 1, tzinfo=UTC)
        db_session.add_all(
            [
                EventRecipient(event_id=event.id, user_id=user.id),
                EventRecipient(event_id=second.id, user_id=user.id, read_at=earlier),
                EventRecipient(event_id=event.id, user_id=other.id),
            ]
        )
        await db_session.flush()

        updated = await EventRepository(db_session).mark_all_read(user.id)

        assert updated == 1
        rows = {
            (row.event_id, row.user_id): row.read_at
            for row in await db_session.scalars(select(EventRecipient))
        }
        assert rows[(event.id, user.id)] is not None
        assert rows[(second.id, user.id)] == earlier
        assert rows[(event.id, other.id)] is None
