from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import Event, EventRecipient
from app.repositories import EventRepository
from tests.factories import ActivatedUserFactory, PostFactory


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
