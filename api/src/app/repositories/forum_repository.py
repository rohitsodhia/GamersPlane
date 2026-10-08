from collections.abc import Collection

from sqlalchemy import ScalarResult, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.models import Forum, User


class ForumRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def add(
        self,
        title: str,
        forum_type: Forum.ForumTypes,
        parent_id: int,
        description: str | None = None,
        game_id: int | None = None,
    ) -> Forum:
        parent_heritage = await self.db_session.scalar(
            select(Forum.heritage).where(Forum.id == parent_id)
        )
        if parent_heritage is None:
            raise NotFoundException(f'Parent forum "{parent_id}" does not exist')

        child_count = await self.db_session.scalar(
            select(func.count()).where(Forum.parent_id == parent_id)
        )
        obj = Forum(
            title=title,
            description=description,
            forum_type=forum_type,
            parent_id=parent_id,
            heritage=parent_heritage + [parent_id],
            order=(child_count or 0) + 1,
            game_id=game_id,
        )
        self.db_session.add(obj)
        await self.db_session.flush()
        return obj

    async def get(self, forum_id: int) -> Forum | None:
        forum = await self.db_session.get(Forum, forum_id)
        return forum

    async def get_multiple(self, forum_ids: list[int]) -> ScalarResult[Forum]:
        return await self.db_session.scalars(
            select(Forum).where(Forum.id.in_(forum_ids))
        )

    async def get_descendants(
        self, forum_id: int, only_game_ids: Collection[int] | None = None
    ) -> ScalarResult[Forum]:
        """Every forum below ``forum_id``.

        ``only_game_ids`` limits game forums to those games; non-game forums are
        unaffected.
        """
        query = (
            select(Forum)
            .where(Forum.heritage.contains([forum_id]))
            .order_by(Forum.order)
        )
        if only_game_ids is not None:
            query = query.where(
                Forum.game_id.is_(None) | Forum.game_id.in_(only_game_ids)
            )
        return await self.db_session.scalars(query)
