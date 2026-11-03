from collections.abc import Collection
from datetime import UTC, datetime, timedelta

from sqlalchemy import Row, and_, delete, func, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    Character,
    Event,
    EventRecipient,
    Game,
    Player,
    Post,
    Thread,
    User,
)


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

    async def upsert_event(
        self,
        type: Event.Types,
        actor_id: int,
        recipient_ids: Collection[int],
        *,
        game_id: int,
        subject_user_id: int | None = None,
        character_id: int | None = None,
    ) -> Event | None:
        """Raise a game event for the recipients, reusing the event with the same
        key (``type`` + ``game_id`` + ``subject_user_id`` for invites and
        applications, ``character_id`` for submissions) when there is one.

        A reused event takes the new actor and the current time, and every current
        recipient gets a fresh unread, undismissed row. Recipients no longer in the
        set keep their rows. With no recipients nothing is written and None is
        returned.
        """
        if not recipient_ids:
            return None
        now = datetime.now(UTC)
        if type is Event.Types.CHARACTER_SUBMITTED:
            key = (Event.character_id == character_id,)
        else:
            key = (
                Event.game_id == game_id,
                Event.subject_user_id == subject_user_id,
            )
        event = await self.db_session.scalar(
            select(Event).where(Event.type == type, *key)
        )
        if event is None:
            event = Event(
                type=type,
                actor_id=actor_id,
                game_id=game_id,
                subject_user_id=subject_user_id,
                character_id=character_id,
                created_at=now,
            )
            self.db_session.add(event)
            await self.db_session.flush()
        else:
            event.actor_id = actor_id
            event.created_at = now
            await self.db_session.flush()
        await self.add_recipients(event.id, recipient_ids)
        await self.db_session.execute(
            update(EventRecipient)
            .where(
                EventRecipient.event_id == event.id,
                EventRecipient.user_id.in_(recipient_ids),
            )
            .values(read_at=None, dismissed_at=None)
            .execution_options(synchronize_session="fetch")
        )
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

    # Reading a user's notifications

    @staticmethod
    def _visible_statement(columns, user_id: int, first_post, subject, gm):
        """``select(*columns)`` over the user's undismissed rows that still hold:

        - mention: the post is published and neither it, its thread, nor the
          thread's first post is deleted. Whether the user can still read the
          forum is for the caller to check, using each row's ``forum_id``.
        - invite: the user is still invited and the game is live (not retired or
          deleted).
        - application: the applicant is still applied, the game is live, and the
          user is still an accepted GM of it.
        - character: the character is still in the event's game, unapproved, and
          not deleted, the game is live, and the user is still an accepted GM.

        ``first_post`` is an alias of Post, ``subject`` and ``gm`` are aliases of
        Player (the event's subject in the game, and the user in the game).
        """
        game_live = and_(
            Game.id.is_not(None), Game.retired.is_(None), Game.deleted.is_(None)
        )
        user_is_gm = and_(gm.is_gm.is_(True), gm.state == Player.States.ACCEPTED)
        mention = and_(
            Event.type == Event.Types.MENTION,
            Post.state == Post.States.PUBLISHED,
            Post.deleted.is_(None),
            Thread.id.is_not(None),
            Thread.deleted.is_(None),
            first_post.id.is_not(None),
            first_post.deleted.is_(None),
        )
        invite = and_(
            Event.type == Event.Types.GAME_INVITE,
            subject.state == Player.States.INVITED,
            game_live,
        )
        application = and_(
            Event.type == Event.Types.GAME_APPLICATION,
            subject.state == Player.States.APPLIED,
            game_live,
            user_is_gm,
        )
        character = and_(
            Event.type == Event.Types.CHARACTER_SUBMITTED,
            Character.id.is_not(None),
            Character.deleted.is_(None),
            Character.game_id == Event.game_id,
            Character.approved.is_(False),
            game_live,
            user_is_gm,
        )
        return (
            select(*columns)
            .select_from(EventRecipient)
            .join(Event, Event.id == EventRecipient.event_id)
            .join(User, User.id == Event.actor_id)
            .outerjoin(Post, Post.id == Event.post_id)
            .outerjoin(Thread, Thread.id == Post.thread_id)
            .outerjoin(first_post, first_post.id == Thread.first_post_id)
            .outerjoin(Game, Game.id == Event.game_id)
            .outerjoin(Character, Character.id == Event.character_id)
            .outerjoin(
                subject,
                and_(
                    subject.game_id == Event.game_id,
                    subject.user_id == Event.subject_user_id,
                ),
            )
            .outerjoin(
                gm,
                and_(
                    gm.game_id == Event.game_id,
                    gm.user_id == EventRecipient.user_id,
                ),
            )
            .where(
                EventRecipient.user_id == user_id,
                EventRecipient.dismissed_at.is_(None),
                or_(mention, invite, application, character),
            )
        )

    @staticmethod
    def cursor_for(created_at: datetime, event_id: int) -> str:
        """The opaque ``before`` value that continues after the given row."""
        micros = (created_at - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(
            microseconds=1
        )
        return f"{micros}_{event_id}"

    @staticmethod
    def parse_cursor(cursor: str) -> tuple[datetime, int]:
        """Inverse of ``cursor_for``; ValueError when it isn't one."""
        micros, event_id = cursor.split("_")
        created_at = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
            microseconds=int(micros)
        )
        return created_at, int(event_id)

    async def get_notification_rows(
        self, user_id: int, limit: int, before: tuple[datetime, int] | None
    ) -> list[Row]:
        """The user's visible notifications of every type, newest first (by
        ``created_at``, then event id), up to ``limit`` of them after the
        ``(created_at, event_id)`` key ``before``. Columns: ``event_id``,
        ``type``, ``created_at``, ``actor_id``, ``actor_username``, ``read_at``,
        ``post_id``, ``thread_id``, ``thread_title``, ``forum_id``, ``game_id``,
        ``game_title``, ``character_id``, ``character_name``; the ones a type
        doesn't use are NULL."""
        # A thread's title is its first post's.
        first_post = aliased(Post)
        subject = aliased(Player)
        gm = aliased(Player)
        statement = (
            self._visible_statement(
                (
                    Event.id.label("event_id"),
                    Event.type,
                    Event.created_at,
                    Event.actor_id,
                    User.username.label("actor_username"),
                    EventRecipient.read_at,
                    Event.post_id,
                    Post.thread_id,
                    first_post.title.label("thread_title"),
                    Thread.forum_id,
                    Event.game_id,
                    Game.title.label("game_title"),
                    Event.character_id,
                    Character.name.label("character_name"),
                ),
                user_id,
                first_post,
                subject,
                gm,
            )
            .order_by(Event.created_at.desc(), Event.id.desc())
            .limit(limit)
        )
        if before is not None:
            statement = statement.where(
                tuple_(Event.created_at, Event.id) < tuple_(*before)
            )
        return list((await self.db_session.execute(statement)).all())

    async def count_unread_by_forum(self, user_id: int) -> dict[int | None, int]:
        """How many unread, still-visible notifications the user has, keyed by the
        forum of a mention's thread; everything that isn't a mention is under
        None. Forums the user can no longer read aren't weeded out here."""
        first_post = aliased(Post)
        rows = await self.db_session.execute(
            self._visible_statement(
                (Thread.forum_id, func.count()),
                user_id,
                first_post,
                aliased(Player),
                aliased(Player),
            )
            .where(EventRecipient.read_at.is_(None))
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
