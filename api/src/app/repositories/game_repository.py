import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.configs import configs
from app.models import Forum, Game, Player, Role, System, User
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

    async def get_player_games(self, user_id: int) -> list[Game]:
        query = (
            select(Game)
            .join(
                Player,
                (Player.game_id == Game.id)
                & (Player.user_id == user_id)
                & (Player.state == Player.States.ACCEPTED),
            )
            .options(selectinload(Game.gm), selectinload(Game.system))
            .order_by(Game.title.asc())
        )
        return list(await self.db_session.scalars(query))

    def _browse_query(self, search: str | None, system_ids: list[str] | None = None):
        query = select(Game).order_by(Game.title.asc())
        if self.principal is not None:
            query = query.where(
                ~select(Player.game_id)
                .where(
                    Player.game_id == Game.id,
                    Player.user_id == self.principal.id,
                    Player.state == Player.States.ACCEPTED,
                )
                .exists()
            )
        if system_ids:
            query = query.where(Game.system_id.in_(system_ids))
        if search:
            query = query.where(Game.title.ilike(f"%{search}%"))
        return query

    async def get_browse(
        self,
        search: str | None = None,
        system_ids: list[str] | None = None,
        page: int = 1,
        limit: int = configs.PAGINATE_PER_PAGE,
    ) -> list[Game]:
        query = (
            self._browse_query(search, system_ids)
            .options(selectinload(Game.gm), selectinload(Game.system))
            .limit(limit)
            .offset((page - 1) * limit)
        )
        return list(await self.db_session.scalars(query))

    async def count_browse(
        self, search: str | None = None, system_ids: list[str] | None = None
    ) -> int:
        query = self._browse_query(search, system_ids)
        return (
            await self.db_session.scalar(
                select(func.count()).select_from(query.subquery())
            )
            or 0
        )

    async def get_player_counts(self, game_ids: list[int]) -> dict[int, int]:
        if not game_ids:
            return {}
        rows = await self.db_session.execute(
            select(Player.game_id, func.count())
            .where(
                Player.game_id.in_(game_ids),
                Player.state == Player.States.ACCEPTED,
                Player.is_gm.is_(False),
            )
            .group_by(Player.game_id)
        )
        return dict(rows.all())

    async def get_principal_gm_game_ids(self, game_ids: list[int]) -> set[int]:
        if self.principal is None or not game_ids:
            return set()
        rows = await self.db_session.scalars(
            select(Player.game_id).where(
                Player.game_id.in_(game_ids),
                Player.user_id == self.principal.id,
                Player.is_gm.is_(True),
            )
        )
        return set(rows)

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

    async def toggle_retire(self, game: Game) -> None:
        if game.retired:
            game.retired = None
        else:
            game.status = Game.Statuses.CLOSED
            game.retired = datetime.now(timezone.utc)

        await self.db_session.flush()
