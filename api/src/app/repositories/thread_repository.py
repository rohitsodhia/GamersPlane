from collections.abc import Collection
from datetime import UTC, datetime

from sqlalchemy import ScalarResult, false, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs import configs
from app.helpers.sql import in_array
from app.models import Forum, Post, Thread, User
from app.repositories.read_tracking_repository import ReadTrackingRepository


class ThreadRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def count_by_forum(self, forum_id: int) -> int:
        return (
            await self.db_session.scalar(
                select(func.count()).where(Thread.forum_id == forum_id)
            )
            or 0
        )

    async def _adjust_forum_counts(
        self, forum_id: int, thread_delta: int = 0, post_delta: int = 0
    ) -> None:
        """Move a forum's counters in SQL, so concurrent writers don't clobber
        each other, then refresh any loaded ``Forum`` so it isn't left stale
        (``thread.forum`` is the same identity-mapped instance)."""
        if not thread_delta and not post_delta:
            return
        await self.db_session.execute(
            update(Forum)
            .where(Forum.id == forum_id)
            .values(
                thread_count=Forum.thread_count + thread_delta,
                post_count=Forum.post_count + post_delta,
            )
            .execution_options(synchronize_session=False)
        )
        forum = await self.db_session.get(Forum, forum_id)
        if forum is not None:
            await self.db_session.refresh(forum, ["thread_count", "post_count"])

    async def get(self, thread_id: int) -> Thread | None:
        thread = await self.db_session.get(Thread, thread_id)
        return thread

    async def get_all(
        self, forum_id: int, page: int = 1, limit: int = configs.PAGINATE_PER_PAGE
    ) -> ScalarResult[Thread] | None:
        threads = await self.db_session.scalars(
            select(Thread)
            .where(Thread.forum_id == forum_id)
            .order_by(
                func.coalesce(Thread.options["sticky"].as_boolean(), false()).desc(),
                Thread.last_post_at.desc().nulls_last(),
                Thread.id.desc(),
            )
            .limit(limit)
            .offset((page - 1) * limit)
        )
        return threads

    async def recently_active_forum_ids(
        self, since: datetime, game_only: bool = False
    ) -> set[int]:
        """The forums holding a live thread whose last post is at or after
        ``since`` (only game forums with ``game_only``)."""
        query = (
            select(Thread.forum_id)
            .join(Forum, Thread.forum_id == Forum.id)
            .where(
                Thread.deleted.is_(None),
                Forum.deleted.is_(None),
                Thread.last_post_at >= since,
            )
            .distinct()
        )
        if game_only:
            query = query.where(Forum.game_id.is_not(None))
        return set(await self.db_session.scalars(query))

    async def get_recent(
        self,
        forum_ids: Collection[int],
        since: datetime,
        page: int = 1,
        limit: int = configs.PAGINATE_PER_PAGE,
        unread_only: bool = False,
    ) -> tuple[list[Thread], int]:
        """A page of the threads in ``forum_ids`` whose last post is at or after
        ``since`` (newest last post first), and how many there are in all.
        ``unread_only`` keeps only those the principal hasn't read.

        ``last_post_at`` is the denormalized time of the thread's last published,
        live post, so a thread with no such post never qualifies.
        """
        if not forum_ids:
            return [], 0
        ids_query = select(Thread.id).where(
            in_array(Thread.forum_id, forum_ids),
            Thread.deleted.is_(None),
            Thread.last_post_at.is_not(None),
            Thread.last_post_at >= since,
        )
        if unread_only:
            ids_query = await ReadTrackingRepository(
                self.db_session, principal=self.principal
            ).only_unread_threads(ids_query, forum_ids)

        count = await self.db_session.scalar(
            select(func.count()).select_from(ids_query.subquery())
        )
        page_ids = list(
            await self.db_session.scalars(
                ids_query.order_by(Thread.last_post_at.desc(), Thread.id.desc())
                .limit(limit)
                .offset((page - 1) * limit)
            )
        )
        loaded = {
            thread.id: thread
            for thread in await self.db_session.scalars(
                select(Thread).where(Thread.id.in_(page_ids))
            )
        }
        return [loaded[thread_id] for thread_id in page_ids], count or 0

    async def create(
        self,
        forum_id: int,
        options: Thread.Options,
    ) -> Thread:
        thread = Thread(forum_id=forum_id, options=options)
        self.db_session.add(thread)
        await self.db_session.flush()
        await self._adjust_forum_counts(forum_id, thread_delta=1)
        return thread

    async def update_options(self, thread: Thread, options: Thread.Options) -> Thread:
        # Assign a new object: in-place changes to a JSON column aren't tracked.
        thread.options = options
        await self.db_session.flush()
        return thread

    async def attach_new_post(self, thread: Thread, post: Post) -> Thread:
        assert post.state == Post.States.PUBLISHED
        if thread.first_post_id is None:
            thread.first_post_id = post.id
        thread.last_post_id = post.id
        thread.last_post_at = post.published_at
        thread.post_count += 1
        await self.db_session.flush()
        await self._adjust_forum_counts(thread.forum_id, post_delta=1)
        return thread

    async def delete(self, thread: Thread) -> Thread:
        thread.deleted = datetime.now(UTC)
        self.db_session.add(thread)
        await self.db_session.flush()
        await self._adjust_forum_counts(
            thread.forum_id, thread_delta=-1, post_delta=-thread.post_count
        )
        return thread

    async def detach_post(self, thread: Thread, post: Post) -> Thread:
        assert post.id != thread.first_post_id
        thread.post_count -= 1
        await self._adjust_forum_counts(thread.forum_id, post_delta=-1)
        if post.id == thread.last_post_id:
            new_last_post = await self.db_session.execute(
                select(Post.id, Post.published_at)
                .where(
                    Post.thread_id == thread.id,
                    Post.state == Post.States.PUBLISHED,
                    Post.id != post.id,
                    Post.deleted.is_(None),
                )
                .order_by(Post.published_at.desc())
                .limit(1)
            )
            row = new_last_post.first()
            thread.last_post_id = row.id if row else None
            thread.last_post_at = row.published_at if row else None
        await self.db_session.flush()
        return thread

    async def get_last_posts_by_forum_ids(
        self, forum_ids: list[int]
    ) -> dict[int, Post | None]:
        threads = await self.db_session.scalars(
            select(Thread)
            .join(Post, Thread.last_post_id == Post.id)
            .where(Thread.forum_id.in_(forum_ids), Thread.last_post_id.isnot(None))
            .order_by(Thread.forum_id, Post.published_at.desc())
            .distinct(Thread.forum_id)
        )
        return {thread.forum_id: thread.last_post for thread in threads}
