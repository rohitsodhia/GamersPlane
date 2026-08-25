import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Forum, Game, Role, System, User
from app.repositories.forum_repository import ForumRepository

GAMES_ROOT_FORUM_ID = 2


class GameRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def get(self, game_id: int) -> Game | None:
        return await self.db_session.scalar(
            select(Game)
            .where(Game.id == game_id)
            .options(
                selectinload(Game.gm),
                selectinload(Game.allowed_char_sheets),
            )
        )

    async def exists(self, game_id: int) -> bool:
        return (
            await self.db_session.scalar(select(Game.id).where(Game.id == game_id))
        ) is not None

    async def create(
        self,
        title: str,
        system_id: str,
        allowed_char_sheets: list[str],
        gm_id: int,
        post_frequency: str,
        num_players: int,
        chars_per_player: int,
        description: dict | None,
        char_gen_info: dict | None,
        public: bool,
        recruitment_thread_id: int | None,
        advanced_options: dict | None,
    ) -> Game:
        char_sheets = await self.db_session.scalars(
            select(System).where(System.id.in_(allowed_char_sheets))
        )

        # Role.name is created from the game's id, which doesn't exist until the
        # game row is flushed, so start with a placeholder and rename it after.
        player_role = Role(name=f"pending-role-{uuid.uuid4()}", owner_id=gm_id)
        self.db_session.add(player_role)
        await self.db_session.flush()

        forum_repository = ForumRepository(self.db_session, auth=[])
        root_forum = await forum_repository.add(
            title=title,
            forum_type=Forum.ForumTypes.FORUM,
            parent_id=GAMES_ROOT_FORUM_ID,
        )

        game = Game(
            title=title,
            system_id=system_id,
            allowed_char_sheets=list(char_sheets),
            gm_id=gm_id,
            num_players=num_players,
            chars_per_player=chars_per_player,
            description=description,
            char_gen_info=char_gen_info,
            root_forum_id=root_forum.id,
            role_id=player_role.id,
            public=public,
            recruitment_thread_id=recruitment_thread_id,
            advanced_options=advanced_options,
        )
        game.post_frequency = post_frequency
        self.db_session.add(game)
        await self.db_session.flush()

        player_role.name = f"Game Id {game.id} Player"
        await self.db_session.flush()

        return game

    async def update(self, game: Game, **kwargs) -> Game:
        for key, value in kwargs.items():
            setattr(game, key, value)
        await self.db_session.flush()
        return game
