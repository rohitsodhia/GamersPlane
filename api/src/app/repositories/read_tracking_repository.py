from collections.abc import Collection, Iterable
from datetime import UTC, datetime

from sqlalchemy import (
    Integer,
    column,
    delete,
    func,
    or_,
    select,
    union,
    values,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import DateTime

from app.models import Forum, ForumRead, Post, Thread, ThreadRead, User
from app.repositories.forum_repository import SITE_ROOT_FORUM_ID


# Stands in for "no cutoff" in unread_forum_ids' VALUES list.
_NO_CUTOFF = datetime.min.replace(tzinfo=UTC)


class ReadTrackingRepository:
    """Per-user forum/thread read state, tracked by ``Post.published_at`` (not
    post id: drafts can be published after later posts).

    A forum's cutoff is the latest ``forum_reads.read_until`` over the forum and
    its ancestors. A thread's read point is its own ``read_until`` or the forum
    cutoff, whichever is later, unless the user pinned it (marked it unread), in
    which case only its own ``read_until`` counts. A thread is unread when its
    ``last_post_at`` is past the read point (or there is no read point).

    ``principal`` is the user whose read state is tracked.
    """

    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    # Reads

    async def forum_cutoff(self, forum: Forum) -> datetime | None:
        """The latest read marker on the forum or any of its ancestors."""
        forum_reads = await self._forum_reads()
        return _cutoff(forum_reads, forum.id, forum.heritage)

    async def thread_read_point(self, thread: Thread) -> datetime | None:
        """Posts published up to this moment are read; None means nothing is."""
        thread_read = await self._thread_read(thread.id)
        forum_reads = await self._forum_reads()
        cutoff = _cutoff(forum_reads, thread.forum_id, thread.forum.heritage)
        return _read_point(thread_read, cutoff)

    async def is_thread_unread(self, thread: Thread) -> bool:
        read_point = await self.thread_read_point(thread)
        return _is_unread(thread.last_post_at, read_point)

    async def unread_thread_ids(self, threads: Collection[Thread]) -> set[int]:
        """The ids of the given threads that have unread posts."""
        if not threads:
            return set()
        thread_reads = {
            row.thread_id: (row.read_until, row.pinned)
            for row in await self.db_session.execute(
                select(
                    ThreadRead.thread_id, ThreadRead.read_until, ThreadRead.pinned
                ).where(
                    ThreadRead.user_id == self.principal.id,
                    ThreadRead.thread_id.in_([thread.id for thread in threads]),
                )
            )
        }
        forum_reads = await self._forum_reads()
        unread = set()
        for thread in threads:
            cutoff = _cutoff(forum_reads, thread.forum_id, thread.forum.heritage)
            read_point = _read_point(thread_reads.get(thread.id), cutoff)
            if _is_unread(thread.last_post_at, read_point):
                unread.add(thread.id)
        return unread

    async def unread_forum_ids(self, readable_forum_ids: Collection[int]) -> set[int]:
        """Which of the readable forums hold an unread thread, directly or in a
        readable subforum. Threads in forums outside the readable set are
        ignored, so a hidden subforum can't make its parent unread."""
        readable = set(readable_forum_ids)
        if not readable:
            return set()

        heritages = {
            row.id: row.heritage
            for row in await self.db_session.execute(
                select(Forum.id, Forum.heritage).where(Forum.id.in_(readable))
            )
        }
        if not heritages:
            return set()
        forum_reads = await self._forum_reads()

        cutoffs = values(
            column("forum_id", Integer),
            column("cutoff", DateTime(timezone=True)),
            name="forum_cutoffs",
        ).data(
            [
                (
                    forum_id,
                    _cutoff(forum_reads, forum_id, heritage) or _NO_CUTOFF,
                )
                for forum_id, heritage in heritages.items()
            ]
        )
        cutoff = cutoffs.c.cutoff
        # The comparisons against the cutoff and the thread's own marker are kept
        # separate (rather than against greatest() of the two), and the cutoff is
        # never NULL (no cutoff is a sentinel before any post), so the planner can
        # use ix_threads_forum_id_last_post_at as a range scan per forum.
        # Soft-deleted threads are excluded explicitly: the session's automatic
        # filter isn't relied on inside a UNION.
        not_pinned = (
            select(Thread.forum_id)
            .join(cutoffs, cutoffs.c.forum_id == Thread.forum_id)
            .outerjoin(
                ThreadRead,
                (ThreadRead.thread_id == Thread.id)
                & (ThreadRead.user_id == self.principal.id),
            )
            .where(
                Thread.deleted.is_(None),
                Thread.last_post_at.is_not(None),
                Thread.last_post_at > cutoff,
                or_(ThreadRead.thread_id.is_(None), ThreadRead.pinned.is_(False)),
                or_(
                    ThreadRead.read_until.is_(None),
                    Thread.last_post_at > ThreadRead.read_until,
                ),
            )
        )
        pinned = (
            select(Thread.forum_id)
            .select_from(ThreadRead)
            .join(Thread, Thread.id == ThreadRead.thread_id)
            .where(
                ThreadRead.user_id == self.principal.id,
                ThreadRead.pinned.is_(True),
                Thread.forum_id.in_(heritages),
                Thread.deleted.is_(None),
                Thread.last_post_at.is_not(None),
                or_(
                    ThreadRead.read_until.is_(None),
                    Thread.last_post_at > ThreadRead.read_until,
                ),
            )
        )
        rows = await self.db_session.scalars(union(not_pinned, pinned))

        unread = set()
        for forum_id in rows:
            unread.add(forum_id)
            unread.update(heritages[forum_id])
        return unread & readable

    # Writes

    async def mark_viewed(self, thread: Thread, up_to: datetime) -> None:
        """Record that the user has seen the thread up to ``up_to`` (a page view,
        or their own new post). Never moves the read point backwards, and leaves
        a pin alone."""
        statement = insert(ThreadRead).values(
            user_id=self.principal.id,
            thread_id=thread.id,
            read_until=up_to,
            pinned=False,
        )
        await self.db_session.execute(
            statement.on_conflict_do_update(
                index_elements=["user_id", "thread_id"],
                set_={
                    "read_until": func.greatest(
                        ThreadRead.read_until, statement.excluded.read_until
                    )
                },
            )
        )

    async def mark_thread_read(self, thread: Thread) -> None:
        if thread.last_post_at is None:
            return
        await self._set_thread_read(thread.id, thread.last_post_at, pinned=False)

    async def mark_thread_unread(self, thread: Thread) -> None:
        """Make the newest post unread again: read up to the second-newest
        published post (nothing, if there is only one), and pin that so a forum
        read marker can't hide it."""
        read_until = await self.db_session.scalar(
            select(Post.published_at)
            .where(
                Post.thread_id == thread.id,
                Post.state == Post.States.PUBLISHED,
                Post.deleted.is_(None),
            )
            .order_by(Post.published_at.desc())
            .offset(1)
            .limit(1)
        )
        await self._set_thread_read(thread.id, read_until, pinned=True)

    async def mark_forum_read(self, forum: Forum) -> None:
        """Mark everything in the forum and its subforums read, and drop the
        threads' individual marks (including pins). Forum 0 is the whole site."""
        forum_ids = select(Forum.id).where(
            or_(Forum.id == forum.id, Forum.heritage.contains([forum.id]))
        )
        latest = await self.db_session.scalar(
            select(func.max(Thread.last_post_at)).where(
                Thread.forum_id.in_(forum_ids), Thread.deleted.is_(None)
            )
        )
        if latest is None:
            return

        statement = insert(ForumRead).values(
            user_id=self.principal.id, forum_id=forum.id, read_until=latest
        )
        await self.db_session.execute(
            statement.on_conflict_do_update(
                index_elements=["user_id", "forum_id"],
                set_={"read_until": statement.excluded.read_until},
            )
        )
        await self.db_session.execute(
            delete(ThreadRead).where(
                ThreadRead.user_id == self.principal.id,
                ThreadRead.thread_id.in_(
                    select(Thread.id).where(Thread.forum_id.in_(forum_ids))
                ),
            )
        )

    async def initialize_for_user(self) -> None:
        """Start a new user with everything existing already read: their
        site-wide marker is the moment they registered."""
        statement = insert(ForumRead).values(
            user_id=self.principal.id,
            forum_id=SITE_ROOT_FORUM_ID,
            read_until=datetime.now(UTC),
        )
        # Calling this again must not move an existing site-wide marker.
        await self.db_session.execute(
            statement.on_conflict_do_nothing(index_elements=["user_id", "forum_id"])
        )

    # Internals

    async def _forum_reads(self) -> dict[int, datetime]:
        # Selects columns, not entities, so nothing stale comes from the identity
        # map after the upserts above (which bypass it).
        return {
            row.forum_id: row.read_until
            for row in await self.db_session.execute(
                select(ForumRead.forum_id, ForumRead.read_until).where(
                    ForumRead.user_id == self.principal.id
                )
            )
        }

    async def _thread_read(self, thread_id: int) -> tuple[datetime | None, bool] | None:
        row = (
            await self.db_session.execute(
                select(ThreadRead.read_until, ThreadRead.pinned).where(
                    ThreadRead.user_id == self.principal.id,
                    ThreadRead.thread_id == thread_id,
                )
            )
        ).first()
        return (row.read_until, row.pinned) if row else None

    async def _set_thread_read(
        self, thread_id: int, read_until: datetime | None, pinned: bool
    ) -> None:
        statement = insert(ThreadRead).values(
            user_id=self.principal.id,
            thread_id=thread_id,
            read_until=read_until,
            pinned=pinned,
        )
        await self.db_session.execute(
            statement.on_conflict_do_update(
                index_elements=["user_id", "thread_id"],
                set_={
                    "read_until": statement.excluded.read_until,
                    "pinned": statement.excluded.pinned,
                },
            )
        )


def _latest(*moments: datetime | None) -> datetime | None:
    present = [moment for moment in moments if moment is not None]
    return max(present) if present else None


def _cutoff(
    forum_reads: dict[int, datetime], forum_id: int, heritage: Iterable[int]
) -> datetime | None:
    return _latest(*(forum_reads.get(fid) for fid in [*heritage, forum_id]))


def _read_point(
    thread_read: tuple[datetime | None, bool] | None, cutoff: datetime | None
) -> datetime | None:
    read_until, pinned = thread_read if thread_read else (None, False)
    return read_until if pinned else _latest(read_until, cutoff)


def _is_unread(last_post_at: datetime | None, read_point: datetime | None) -> bool:
    return last_post_at is not None and (
        read_point is None or last_post_at > read_point
    )
