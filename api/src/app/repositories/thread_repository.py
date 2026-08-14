from datetime import UTC, datetime

from sqlalchemy import ScalarResult, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs import configs
from app.models import Post, Thread


class ThreadRepository:
    def __init__(self, db_session: AsyncSession, auth: list[str]):
        self.db_session = db_session
        self.auth = auth

    async def count_by_forum(self, forum_id: int) -> int:
        return (
            await self.db_session.scalar(
                select(func.count()).where(Thread.forum_id == forum_id)
            )
            or 0
        )

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
                Thread.created_at.desc(),
            )
            .limit(limit)
            .offset((page - 1) * limit)
        )
        return threads

    async def create(
        self,
        forum_id: int,
        options: Thread.Options,
    ) -> Thread:
        thread = Thread(forum_id=forum_id, options=options)
        self.db_session.add(thread)
        await self.db_session.flush()
        return thread

    async def attach_new_post(self, thread: Thread, post: Post) -> Thread:
        assert post.state == Post.States.PUBLISHED
        if thread.first_post_id is None:
            thread.first_post_id = post.id
        thread.last_post_id = post.id
        thread.post_count += 1
        await self.db_session.flush()
        return thread

    async def delete(self, thread: Thread) -> Thread:
        thread.deleted = datetime.now(UTC)
        self.db_session.add(thread)
        await self.db_session.flush()
        return thread

    async def detach_post(self, thread: Thread, post: Post) -> Thread:
        assert post.id != thread.first_post_id
        thread.post_count -= 1
        if post.id == thread.last_post_id:
            new_last_post_id = await self.db_session.scalar(
                select(Post.id)
                .where(
                    Post.thread_id == thread.id,
                    Post.state == Post.States.PUBLISHED,
                    Post.id != post.id,
                    Post.deleted.is_(None),
                )
                .order_by(Post.published_at.desc())
                .limit(1)
            )
            thread.last_post_id = new_last_post_id
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
