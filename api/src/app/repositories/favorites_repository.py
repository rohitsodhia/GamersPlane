from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FavoriteGame, User


class FavoritesRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def toggle_game_favorite(self, game_id: int):
        pk = (self.principal.id, game_id)
        existing = await self.db_session.get(FavoriteGame, pk)

        if existing:
            await self.db_session.delete(existing)
            await self.db_session.flush()
            return False

        self.db_session.add(FavoriteGame(user_id=self.principal.id, game_id=game_id))
        await self.db_session.flush()
        return True

    async def get_game_favorite_status(self, game_id: int):
        favorite = await self.db_session.get(FavoriteGame, (self.principal.id, game_id))
        return favorite is not None

    async def get_favorited_game_ids(self, game_ids: list[int]) -> set[int]:
        if not game_ids:
            return set()
        rows = await self.db_session.scalars(
            select(FavoriteGame.game_id).where(
                FavoriteGame.user_id == self.principal.id,
                FavoriteGame.game_id.in_(game_ids),
            )
        )
        return set(rows)
