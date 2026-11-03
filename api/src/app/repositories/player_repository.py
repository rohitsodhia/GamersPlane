from collections.abc import Iterable

from sqlalchemy import ScalarResult, Select, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Character, Forum, Game, Player, Role, User, UserRole
from app.repositories.read_tracking_repository import ReadTrackingRepository


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

    async def get_gm_ids(self, game_id: int) -> list[int]:
        """User ids of the game's accepted GMs, the primary GM included."""
        return list(
            (
                await self.db_session.scalars(
                    select(Player.user_id).where(
                        Player.game_id == game_id,
                        Player.is_gm.is_(True),
                        Player.state == Player.States.ACCEPTED,
                    )
                )
            ).all()
        )

    async def get_player(self, game_id: int, user_id: int) -> Player | None:
        return await self.db_session.get(
            Player, {"game_id": game_id, "user_id": user_id}
        )

    async def update_state(
        self,
        player: Player,
        state: Player.States | None = None,
        is_gm: bool | None = None,
    ) -> None:
        newly_accepted = (
            state is Player.States.ACCEPTED
            and player.state is not Player.States.ACCEPTED
        )
        promoted = is_gm is True and not player.is_gm
        demoted = is_gm is False and player.is_gm
        if state is not None:
            player.state = state
        if is_gm is not None:
            player.is_gm = is_gm

        if newly_accepted or promoted or demoted:
            gm_role_id, player_role_id, root_forum_id = (
                await self.db_session.execute(
                    select(
                        Game.gm_role_id, Game.player_role_id, Game.root_forum_id
                    ).where(Game.id == player.game_id)
                )
            ).one()
            if promoted:
                # A GM's moderate grant covers everything a player role gives,
                # so they hold the GM role in place of any player roles.
                await self._remove_from_game_roles(player, keep_role_id=gm_role_id)
                await self._add_to_role(player.user_id, gm_role_id)
            elif demoted:
                # Only accepted players can be GMs, so a demoted GM is a player.
                await self._remove_from_roles(player.user_id, [gm_role_id])
                await self._add_to_role(player.user_id, player_role_id)
            elif newly_accepted:
                await self._add_to_role(
                    player.user_id, gm_role_id if player.is_gm else player_role_id
                )
            if newly_accepted:
                # Joining opens the game's forums; start them as if the player
                # had marked them all read, rather than with the whole backlog.
                root_forum = await self.db_session.get(Forum, root_forum_id)
                user = await self.db_session.get(User, player.user_id)
                assert root_forum is not None and user is not None
                await ReadTrackingRepository(
                    self.db_session, principal=user
                ).mark_forum_read(root_forum)
        await self.db_session.flush()

    async def _add_to_role(self, user_id: int, role_id: int) -> None:
        """Idempotent; revives the membership if it was soft-deleted."""
        await self.db_session.execute(
            insert(UserRole)
            .values(user_id=user_id, role_id=role_id)
            .on_conflict_do_update(
                index_elements=[UserRole.user_id, UserRole.role_id],
                set_={"deleted": None},
            )
        )

    async def _remove_from_roles(
        self, user_id: int, role_ids: Iterable[int] | Select
    ) -> None:
        await self.db_session.execute(
            delete(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id.in_(role_ids)
            )
        )

    async def _remove_from_game_roles(
        self, player: Player, keep_role_id: int | None = None
    ) -> None:
        """Drop the player's membership in every role scoped to their game."""
        game_role_ids = select(Role.id).where(Role.game_role == player.game_id)
        if keep_role_id is not None:
            game_role_ids = game_role_ids.where(Role.id != keep_role_id)
        await self._remove_from_roles(player.user_id, game_role_ids)

    async def get_attention_items(self, user_id: int) -> dict:
        """Derived header-bell items for the user, from existing state only.

        ``pending`` lists the live games the user runs that have applicants or
        submitted-but-unapproved characters waiting; ``invites`` lists the live
        games the user has been invited to.
        """
        applied = (
            select(func.count())
            .select_from(Player)
            .where(Player.game_id == Game.id, Player.state == Player.States.APPLIED)
            .correlate(Game)
            .scalar_subquery()
        )
        unapproved = (
            select(func.count())
            .select_from(Character)
            .where(Character.game_id == Game.id, Character.approved.is_(False))
            .correlate(Game)
            .scalar_subquery()
        )
        pending_rows = await self.db_session.execute(
            select(Game.id, Game.title, applied, unapproved)
            .join(Player, Player.game_id == Game.id)
            .where(
                Player.user_id == user_id,
                Player.is_gm.is_(True),
                Player.state == Player.States.ACCEPTED,
                Game.retired.is_(None),
            )
            .order_by(Game.title, Game.id)
        )
        invite_rows = await self.db_session.execute(
            select(Game.id, Game.title)
            .join(Player, Player.game_id == Game.id)
            .where(
                Player.user_id == user_id,
                Player.state == Player.States.INVITED,
                Game.retired.is_(None),
            )
            .order_by(Game.title, Game.id)
        )
        return {
            "pending": [
                {
                    "gameId": game_id,
                    "title": title,
                    "players": players,
                    "characters": characters,
                }
                for game_id, title, players, characters in pending_rows
                if players or characters
            ],
            "invites": [
                {"gameId": game_id, "title": title} for game_id, title in invite_rows
            ],
        }

    async def is_gm(self, game_id: int, user_id: int) -> bool:
        player = await self.get_player(game_id, user_id)
        return player is not None and player.is_gm

    async def is_member(self, game_id: int, user_id: int) -> bool:
        """Whether the user is an accepted player (GMs included) of the game."""
        player = await self.get_player(game_id, user_id)
        return player is not None and player.state is Player.States.ACCEPTED

    async def delete_player(self, player: Player) -> None:
        """Remove the player and their membership in every role scoped to the game."""
        await self._remove_from_game_roles(player)
        await self.db_session.delete(player)
        await self.db_session.flush()
