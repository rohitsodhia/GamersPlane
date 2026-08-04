from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Publisher


class PublisherRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add(self, name: str, website: str | None) -> Publisher:
        publisher = Publisher(name=name, website=website)
        self.db_session.add(publisher)
        await self.db_session.flush()
        return publisher

    async def get_all(self) -> list[Publisher]:
        result = await self.db_session.scalars(select(Publisher))
        return list(result.all())
