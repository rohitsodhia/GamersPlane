from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Genre


class GenreRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add(self, genre: str) -> Genre:
        obj = Genre(genre=genre)
        self.db_session.add(obj)
        await self.db_session.flush()
        return obj

    async def get_all(self) -> list[Genre]:
        result = await self.db_session.scalars(select(Genre))
        return list(result.all())
