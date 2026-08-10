from sqlalchemy import ScalarResult, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs import configs
from app.models import Thread


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

    async def get_all(
        self, forum_id: int, page: int = 1, limit: int = configs.PAGINATE_PER_PAGE
    ) -> ScalarResult[Thread] | None:
        threads = await self.db_session.scalars(
            select(Thread)
            .where(Thread.forum_id == forum_id)
            .limit(limit)
            .offset((page - 1) * limit)
        )
        return threads
