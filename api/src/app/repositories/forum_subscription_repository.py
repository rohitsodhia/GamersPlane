from collections.abc import Collection
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Forum,
    ForumRead,
    ForumSubscription,
    ForumSubscriptionNotice,
    Thread,
    ThreadRead,
    User,
    UserMeta,
)
from app.models.user_meta import DEFAULT_FORUM_SUB_TYPE
from app.repositories.read_tracking_repository import _latest, _read_point

SubscriptionKind = Literal["thread", "forum"]


class ForumSubscriptionRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    # A user's own subscriptions

    async def is_subscribed(
        self, user_id: int, *, forum_id: int | None = None, thread_id: int | None = None
    ) -> bool:
        """Whether the user subscribes directly to this forum or this thread."""
        return (
            await self.db_session.scalar(
                select(ForumSubscription.id).where(
                    ForumSubscription.user_id == user_id,
                    ForumSubscription.forum_id == forum_id
                    if forum_id is not None
                    else ForumSubscription.thread_id == thread_id,
                )
            )
            is not None
        )

    async def add(
        self, user_id: int, *, forum_id: int | None = None, thread_id: int | None = None
    ) -> None:
        """Subscribe; already being subscribed is fine."""
        await self.db_session.execute(
            insert(ForumSubscription)
            .values(user_id=user_id, forum_id=forum_id, thread_id=thread_id)
            .on_conflict_do_nothing()
        )

    async def remove(
        self, user_id: int, *, forum_id: int | None = None, thread_id: int | None = None
    ) -> None:
        """Unsubscribe; not being subscribed is fine."""
        await self.db_session.execute(
            delete(ForumSubscription).where(
                ForumSubscription.user_id == user_id,
                ForumSubscription.forum_id == forum_id
                if forum_id is not None
                else ForumSubscription.thread_id == thread_id,
            )
        )

    async def get_for_user(self, user_id: int) -> tuple[list[int], list[int]]:
        """The ids of the forums and of the threads the user is subscribed to."""
        rows = await self.db_session.execute(
            select(ForumSubscription.forum_id, ForumSubscription.thread_id)
            .where(ForumSubscription.user_id == user_id)
            .order_by(ForumSubscription.id)
        )
        forum_ids, thread_ids = [], []
        for forum_id, thread_id in rows:
            if forum_id is not None:
                forum_ids.append(forum_id)
            else:
                thread_ids.append(thread_id)
        return forum_ids, thread_ids

    # Who to notify

    async def subscribers(self, thread: Thread) -> dict[int, SubscriptionKind]:
        """Each user subscribed to the thread, or to its forum directly (not an
        ancestor), with which kind of subscription applies. A user with both gets
        "thread"."""
        rows = await self.db_session.execute(
            select(ForumSubscription.user_id, ForumSubscription.thread_id).where(
                or_(
                    ForumSubscription.thread_id == thread.id,
                    ForumSubscription.forum_id == thread.forum_id,
                )
            )
        )
        kinds: dict[int, SubscriptionKind] = {}
        for user_id, thread_id in rows:
            if thread_id is not None:
                kinds[user_id] = "thread"
            else:
                kinds.setdefault(user_id, "forum")
        return kinds

    async def deliverable_users(
        self, user_ids: Collection[int]
    ) -> list[tuple[User, str]]:
        """The given users who can be mailed (activated, not banned, not
        suspended) with their forumSubType; a missing row reads as the default."""
        if not user_ids:
            return []
        now = datetime.now(UTC)
        mode = (
            select(UserMeta._value)
            .where(
                UserMeta.user_id == User.id,
                UserMeta.key == UserMeta.MetaKeys.FORUM_SUB_TYPE.value,
            )
            .limit(1)
            .scalar_subquery()
        )
        rows = await self.db_session.execute(
            select(User, mode)
            .where(
                User.id.in_(user_ids),
                User.activated_on.is_not(None),
                User.banned.is_(None),
                or_(User.suspended_until.is_(None), User.suspended_until <= now),
            )
            .order_by(User.id)
        )
        return [(user, stored or DEFAULT_FORUM_SUB_TYPE) for user, stored in rows]

    async def users_due_notice(
        self, thread: Thread, user_ids: Collection[int]
    ) -> set[int]:
        """The users who may be emailed about the thread again.

        A user is due if they've never been emailed about it, or have read it since.
        "Read since" follows the read tracking, which works in post
        ``published_at`` terms: the notice records ``notified_through``, the
        ``published_at`` of the newest post it covered, and the user has read what
        it told them about once their read point for the thread has reached that
        moment. The read point is the same one the thread's unread marker uses: the
        later of their own ``thread_reads.read_until`` and the ``forum_reads``
        cutoff over the thread's forum and its ancestors (the cutoff is ignored when
        they pinned the thread by marking it unread). Posts published after that
        point are unread, so a user who hasn't reached it is still "unvisited" and
        is not emailed again.
        """
        if not user_ids:
            return set()
        notices = {
            user_id: through
            for user_id, through in await self.db_session.execute(
                select(
                    ForumSubscriptionNotice.user_id,
                    ForumSubscriptionNotice.notified_through,
                ).where(
                    ForumSubscriptionNotice.thread_id == thread.id,
                    ForumSubscriptionNotice.user_id.in_(user_ids),
                )
            )
        }
        due = set(user_ids) - set(notices)
        if not notices:
            return due

        thread_reads = {
            row.user_id: (row.read_until, row.pinned)
            for row in await self.db_session.execute(
                select(
                    ThreadRead.user_id, ThreadRead.read_until, ThreadRead.pinned
                ).where(
                    ThreadRead.thread_id == thread.id,
                    ThreadRead.user_id.in_(notices),
                )
            )
        }
        # Looked up by id: a thread created in this request hasn't loaded ``forum``.
        forum = await self.db_session.get(Forum, thread.forum_id)
        assert forum is not None
        cutoffs: dict[int, datetime | None] = {}
        for user_id, read_until in await self.db_session.execute(
            select(ForumRead.user_id, ForumRead.read_until).where(
                ForumRead.user_id.in_(notices),
                ForumRead.forum_id.in_([*forum.heritage, forum.id]),
            )
        ):
            cutoffs[user_id] = _latest(cutoffs.get(user_id), read_until)

        for user_id, through in notices.items():
            read_point = _read_point(thread_reads.get(user_id), cutoffs.get(user_id))
            if read_point is not None and read_point >= through:
                due.add(user_id)
        return due

    async def record_notices(
        self, thread: Thread, user_ids: Collection[int], through: datetime
    ) -> None:
        """Note that these users were just emailed about the thread's content up
        to ``through``."""
        if not user_ids:
            return
        now = datetime.now(UTC)
        statement = insert(ForumSubscriptionNotice).values(
            [
                {
                    "user_id": user_id,
                    "thread_id": thread.id,
                    "notified_at": now,
                    "notified_through": through,
                }
                for user_id in user_ids
            ]
        )
        await self.db_session.execute(
            statement.on_conflict_do_update(
                index_elements=["user_id", "thread_id"],
                set_={
                    "notified_at": statement.excluded.notified_at,
                    "notified_through": statement.excluded.notified_through,
                },
            )
        )

    # The Manage Subscriptions page

    async def get_subscribed_threads(self, thread_ids: Collection[int]) -> list[Thread]:
        if not thread_ids:
            return []
        return list(
            await self.db_session.scalars(
                select(Thread).where(Thread.id.in_(thread_ids))
            )
        )
