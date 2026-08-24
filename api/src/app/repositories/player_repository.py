from sqlalchemy import ScalarResult, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Player, User


class DuplicatePlayerError(Exception):
    def __init__(self, game_id: int, user_id: int) -> None:
        self.game_id = game_id
        self.user_id = user_id
        super().__init__(f"User {user_id} is already a player in game {game_id}")


class PlayerRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def attach_player_to_game(
        self,
        game_id: int,
        user_id: int,
        is_gm: bool = False,
        state: Player.States = Player.States.APPLIED,
    ) -> Player:
        player = Player(
            game_id=game_id,
            user_id=user_id,
            is_gm=is_gm,
            state=state,
        )
        self.db_session.add(player)
        try:
            await self.db_session.flush()
        except IntegrityError as e:
            raise DuplicatePlayerError(game_id, user_id) from e
        return player

    async def get_players_for_game(
        self, game_id: int, only_accepted: bool = False
    ) -> ScalarResult[Player]:
        query = (
            select(Player)
            .where(Player.game_id == game_id)
            .options(selectinload(Player.user))
        )
        if only_accepted:
            query = query.where(Player.state == Player.States.ACCEPTED)
        return await self.db_session.scalars(query)

    async def get_player(self, game_id: int, user_id: int) -> Player | None:
        return await self.db_session.get(
            Player, {"game_id": game_id, "user_id": user_id}
        )

    async def is_gm(self, game_id: int, user_id: int) -> bool:
        player = await self.get_player(game_id, user_id)
        return player is not None and player.is_gm

    async def delete_player(self, player: Player) -> None:
        await self.db_session.delete(player)
        await self.db_session.flush()
