from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
