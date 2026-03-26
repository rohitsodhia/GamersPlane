from __future__ import annotations

from typing import Literal

from sqlalchemy import func, select

from app.configs import configs
from app.database import DBSessionDependency
from app.models.legacy import System


class NoRecipientException(Exception):
    def __init__(self):
        super().__init__("No recipient found")


class SystemRepository:
    def __init__(
        self,
        db_session: DBSessionDependency,
    ):
        self.db_session = db_session

    async def get_systems(
        self,
        *,
        page: int = 1,
        limit: int = configs.PAGINATE_PER_PAGE,
        sort: Literal["asc", "desc"] = "asc",
    ):
        statement = (
            select(System)
            .limit(limit)
            .offset((page - 1) * limit)
            .order_by(
                System.sort_name.asc() if sort == "asc" else System.sort_name.desc()
            )
        )

        pms = await self.db_session.scalars(statement)

        return pms

    async def count_systems(self):
        return await self.db_session.scalar(select(func.count(System.id)))

    async def get_system(self, system_id: int):
        system = await self.db_session.scalar(
            select(System).where(System.id == system_id).limit(1)
        )
        return system
