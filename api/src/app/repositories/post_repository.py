from sqlalchemy import ScalarResult, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.configs import configs
from app.models import Post, User


class PostRepository:
    def __init__(self, db_session: AsyncSession, auth: list[str]):
        self.db_session = db_session
        self.auth = auth

    async def count_by_thread(self, thread_id: int) -> int:
        return (
            await self.db_session.scalar(
                select(func.count()).where(
                    Post.thread_id == thread_id, Post.state == Post.States.PUBLISHED
                )
            )
            or 0
        )

    async def get(self, post_id: int) -> Post | None:
        post = await self.db_session.get(Post, post_id)
        return post

    async def get_page_number(
        self, post: Post, limit: int = configs.PAGINATE_PER_PAGE
    ) -> int:
        if post.published_at is None:
            return 1

        position = (
            await self.db_session.scalar(
                select(func.count()).where(
                    Post.thread_id == post.thread_id,
                    Post.state == Post.States.PUBLISHED,
                    Post.published_at < post.published_at,
                )
            )
            or 0
        )
        return position // limit + 1

    async def get_all(
        self, thread_id: int, page: int = 1, limit: int = configs.PAGINATE_PER_PAGE
    ) -> ScalarResult[Post]:
        return await self.db_session.scalars(
            select(Post)
            .where(Post.thread_id == thread_id, Post.state == Post.States.PUBLISHED)
            .options(selectinload(Post.author).selectinload(User.meta))
            .order_by(Post.published_at)
            .limit(limit)
            .offset((page - 1) * limit)
        )

    async def create(
        self,
        thread_id: int,
        author_id: int,
        title: str,
        body: dict,
        state: Post.States = Post.States.DRAFT,
    ) -> Post:
        post = Post(
            thread_id=thread_id,
            author_id=author_id,
            title=title,
            body=body,
            state=state,
        )
        self.db_session.add(post)
        await self.db_session.flush()
        return post

    async def update(self, post: Post, title: str, body: dict) -> Post:
        post.title = title
        post.body = body
        self.db_session.add(post)
        await self.db_session.flush()
        return post
