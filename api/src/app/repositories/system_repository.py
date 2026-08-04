from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Genre, System


class SystemRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get(self, only_enabled: bool = True):
        query = (
            select(System)
            .order_by(System.sort_name)
            .options(selectinload(System.publisher), selectinload(System.genres))
        )
        if only_enabled:
            query = query.where(System.enabled)
        return await self.db_session.scalars(query)

    async def add(
        self,
        id: str,
        name: str,
        sort_name: str,
        publisher_id: int,
        genres: list[Genre],
        basics: list[dict],
        has_char_sheet: bool = False,
        enabled: bool = True,
    ) -> System:
        system = System(
            id=id,
            name=name,
            sort_name=sort_name,
            publisher_id=publisher_id,
            genres=genres,
            basics=basics,
            has_char_sheet=has_char_sheet,
            enabled=enabled,
        )
        self.db_session.add(system)
        await self.db_session.flush()
        return system
