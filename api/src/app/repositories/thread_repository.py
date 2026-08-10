from sqlalchemy import ScalarResult, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Thread


class ThreadRepository:
    def __init__(self, db_session: AsyncSession, auth: list[str]):
        self.db_session = db_session
        self.auth = auth

    async def get_all(self, forum_id: int) -> ScalarResult[Thread] | None:
        threads = await self.db_session.scalars(
            select(Thread).where(Thread.forum_id == forum_id)
        )
        return threads
