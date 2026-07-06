from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Genre, System


class SystemRepository:
    def __init__(self, db_session):
        self.db_session = db_session

    async def get(self):
        return await self.db_session.scalars(
            select(System).options(
                selectinload(System.publisher), selectinload(System.genres)
            )
        )

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
