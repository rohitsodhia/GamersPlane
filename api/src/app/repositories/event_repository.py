from collections.abc import Collection
from datetime import UTC, datetime

from sqlalchemy import Row, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Event, EventRecipient, Post, Thread, User


class EventRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    # Writing events

    async def get_post_event(self, post_id: int, type: Event.Types) -> Event | None:
        return await self.db_session.scalar(
            select(Event).where(Event.post_id == post_id, Event.type == type)
        )

    async def get_recipient_ids(self, event_id: int) -> set[int]:
        """Everyone with a row for the event, read or not."""
        rows = await self.db_session.scalars(
            select(EventRecipient.user_id).where(EventRecipient.event_id == event_id)
        )
        return set(rows)

    async def create_event(
        self, type: Event.Types, actor_id: int, post_id: int, thread_id: int
    ) -> Event:
        event = Event(
            type=type, actor_id=actor_id, post_id=post_id, thread_id=thread_id
        )
        self.db_session.add(event)
        await self.db_session.flush()
        return event

    async def add_recipients(self, event_id: int, user_ids: Collection[int]) -> None:
        """Give each user an unread row; one that already has a row is left alone."""
        if not user_ids:
            return
        await self.db_session.execute(
            insert(EventRecipient)
            .values([{"event_id": event_id, "user_id": uid} for uid in user_ids])
            .on_conflict_do_nothing()
        )

    async def remove_recipients(self, event_id: int, user_ids: Collection[int]) -> None:
        if not user_ids:
            return
        await self.db_session.execute(
            delete(EventRecipient)
            .where(
                EventRecipient.event_id == event_id,
                EventRecipient.user_id.in_(user_ids),
            )
            .execution_options(synchronize_session="fetch")
        )

    async def delete_event(self, event_id: int) -> None:
        """Delete the event; its recipient rows go with it."""
        await self.db_session.execute(
            delete(Event)
            .where(Event.id == event_id)
            .execution_options(synchronize_session="fetch")
        )

    async def get_notifiable_users(self, user_ids: Collection[int]) -> list[User]:
        """The given users who exist and aren't banned or suspended."""
        if not user_ids:
            return []
        now = datetime.now(UTC)
        result = await self.db_session.scalars(
            select(User)
            .where(
                User.id.in_(user_ids),
                User.banned.is_(None),
                or_(User.suspended_until.is_(None), User.suspended_until <= now),
            )
            .order_by(User.id)
        )
        return list(result)

    # Reading a user's mentions

    @staticmethod
    def _visible(user_id: int, first_post):
        """Conditions for the user's mention rows whose post is still published and
        whose post and thread aren't deleted. Whether they can still read the
        forum is for the caller to check, using each row's ``forum_id``."""
        return (
            EventRecipient.user_id == user_id,
            Event.type == Event.Types.MENTION,
            Post.state == Post.States.PUBLISHED,
            Post.deleted.is_(None),
            Thread.deleted.is_(None),
            first_post.deleted.is_(None),
            EventRecipient.dismissed_at.is_(None),
        )

    async def get_mention_rows(
        self, user_id: int, limit: int, before: int | None
    ) -> list[Row]:
        """The user's mentions, newest first, up to ``limit`` of them after the
        event id ``before``: ``event_id``, ``created_at``, ``actor_id``,
        ``actor_username``, ``post_id``, ``thread_id``, ``thread_title``,
        ``forum_id``, ``read_at``."""
        # A thread's title is its first post's.
        first_post = aliased(Post)
        statement = (
            select(
                Event.id.label("event_id"),
                Event.created_at,
                Event.actor_id,
                User.username.label("actor_username"),
                Event.post_id,
                Post.thread_id,
                first_post.title.label("thread_title"),
                Thread.forum_id,
                EventRecipient.read_at,
            )
            .select_from(EventRecipient)
            .join(Event, Event.id == EventRecipient.event_id)
            .join(Post, Post.id == Event.post_id)
            .join(Thread, Thread.id == Post.thread_id)
            .join(first_post, first_post.id == Thread.first_post_id)
            .join(User, User.id == Event.actor_id)
            .where(*self._visible(user_id, first_post))
            .order_by(Event.created_at.desc(), Event.id.desc())
            .limit(limit)
        )
        if before is not None:
            statement = statement.where(Event.id < before)
        return list((await self.db_session.execute(statement)).all())

    async def count_unread_mentions_by_forum(self, user_id: int) -> dict[int, int]:
        """How many unread, still-visible mentions the user has in each forum
        (forums they can no longer read aren't weeded out here)."""
        first_post = aliased(Post)
        rows = await self.db_session.execute(
            select(Thread.forum_id, func.count())
            .select_from(EventRecipient)
            .join(Event, Event.id == EventRecipient.event_id)
            .join(Post, Post.id == Event.post_id)
            .join(Thread, Thread.id == Post.thread_id)
            .join(first_post, first_post.id == Thread.first_post_id)
            .where(
                *self._visible(user_id, first_post),
                EventRecipient.read_at.is_(None),
            )
            .group_by(Thread.forum_id)
        )
        return {forum_id: count for forum_id, count in rows}

    # Marking read

    async def mark_read(self, user_id: int, event_id: int) -> bool:
        """Mark the user's row for the event read (a row already read keeps its
        time). False when the user has no row for it."""
        recipient = await self.db_session.get(EventRecipient, (event_id, user_id))
        if recipient is None:
            return False
        if recipient.read_at is None:
            recipient.read_at = datetime.now(UTC)
            await self.db_session.flush()
        return True

    async def dismiss(self, user_id: int, event_id: int) -> bool:
        """Dismiss the user's row for the event, which also reads it (rows already
        read or dismissed keep their times). False when the user has no row."""
        recipient = await self.db_session.get(EventRecipient, (event_id, user_id))
        if recipient is None:
            return False
        now = datetime.now(UTC)
        if recipient.read_at is None:
            recipient.read_at = now
        if recipient.dismissed_at is None:
            recipient.dismissed_at = now
        await self.db_session.flush()
        return True

    async def dismiss_for_posts(
        self, user_id: int, thread_id: int, post_ids: Collection[int]
    ) -> int:
        """Dismiss (and read) the user's mention rows for the given posts, counting
        only published posts that belong to the thread. How many rows changed."""
        if not post_ids:
            return 0
        now = datetime.now(UTC)
        events = (
            select(Event.id)
            .join(Post, Post.id == Event.post_id)
            .where(
                Event.type == Event.Types.MENTION,
                Event.post_id.in_(post_ids),
                Post.thread_id == thread_id,
                Post.state == Post.States.PUBLISHED,
            )
        )
        result = await self.db_session.execute(
            update(EventRecipient)
            .where(
                EventRecipient.user_id == user_id,
                EventRecipient.dismissed_at.is_(None),
                EventRecipient.event_id.in_(events),
            )
            .values(
                dismissed_at=now,
                read_at=func.coalesce(EventRecipient.read_at, now),
            )
            .execution_options(synchronize_session="fetch")
        )
        return result.rowcount  # type: ignore[attr-defined]

    async def mark_all_read(self, user_id: int) -> int:
        """Mark every unread row of the user's read; how many there were."""
        result = await self.db_session.execute(
            update(EventRecipient)
            .where(EventRecipient.user_id == user_id, EventRecipient.read_at.is_(None))
            .values(read_at=datetime.now(UTC))
            .execution_options(synchronize_session="fetch")
        )
        return result.rowcount  # type: ignore[attr-defined]
