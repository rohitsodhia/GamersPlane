from collections.abc import Sequence

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationError,
)
from app.forums.permissions import FORUM_VERBS_ORDERED, ForumPermissions
from app.models import Forum, Game, Player, Role, RolePermission, User
from app.repositories.rbac_repository import RBACkRepository

Verbs = RolePermission.ValidPermissions
Effects = RolePermission.Effects
ScopeTypes = RolePermission.ScopeTypes

ROLE_SEARCH_LIMIT = 20

# role id -> forum id -> that role's (verb, effect) grants there
GrantsByRole = dict[int, dict[int, list[tuple[Verbs, Effects]]]]


class ForumACPRepository:
    """Data access for the forum ACP: the permissions grid and a game's roles."""

    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def get_game(self, game_id: int) -> Game:
        game = await self.db_session.get(Game, game_id)
        if game is None:
            raise NotFoundException("Game not found")
        return game

    async def _eligible_conditions(self, forum: Forum) -> list:
        """Filters on ``Role`` for the roles whose grants this forum's grid may
        edit. A game's GM role and the Admin role are locked, so never eligible."""
        if forum.game_id is not None:
            game = await self.get_game(forum.game_id)
            return [Role.game_role == game.id, Role.id != game.gm_role_id]
        return [Role.game_role.is_(None), Role.id != Role.ADMIN_ID]

    async def _load_grants(
        self, role_ids: Sequence[int], forum_ids: Sequence[int]
    ) -> GrantsByRole:
        """Every forum grant the roles hold on any of the forums, in one query."""
        if not role_ids or not forum_ids:
            return {}
        rows = await self.db_session.execute(
            select(
                RolePermission.role_id,
                RolePermission.scope_id,
                RolePermission.permission,
                RolePermission.effect,
            )
            .join(Role)
            .where(
                RolePermission.scope_type == ScopeTypes.FORUM,
                RolePermission.role_id.in_(role_ids),
                RolePermission.scope_id.in_(forum_ids),
            )
        )
        grants: GrantsByRole = {}
        for role_id, scope_id, permission, effect in rows:
            grants.setdefault(role_id, {}).setdefault(scope_id, []).append(
                (permission, effect)
            )
        return grants

    async def get_permission_rows(
        self, forum: Forum
    ) -> list[tuple[Role, str, dict[str, str], dict[str, bool]]]:
        """The roles listed in a forum's permissions grid, each as
        ``(role, kind, grants on this forum, inherited verbs)``.

        A game forum lists all the game's roles (Player first). Any other forum
        lists Registered and Guest plus the site roles with a grant here.
        """
        conditions = await self._eligible_conditions(forum)
        query = select(Role).where(*conditions)
        game = None
        if forum.game_id is not None:
            game = await self.get_game(forum.game_id)
            query = query.order_by(
                case((Role.id == game.player_role_id, 0), else_=1), Role._name
            )
        else:
            granted_here = select(RolePermission.role_id).where(
                RolePermission.scope_type == ScopeTypes.FORUM,
                RolePermission.scope_id == forum.id,
            )
            query = query.where(
                or_(
                    Role.id.in_([Role.REGISTERED_ID, Role.GUEST_ID]),
                    Role.id.in_(granted_here),
                )
            ).order_by(
                case(
                    (Role.id == Role.REGISTERED_ID, 0),
                    (Role.id == Role.GUEST_ID, 1),
                    else_=2,
                ),
                Role._name,
            )
        roles = list((await self.db_session.scalars(query)).all())

        chain = [*forum.heritage, forum.id]
        grants = await self._load_grants([role.id for role in roles], chain)

        result = []
        for role in roles:
            role_grants = grants.get(role.id, {})
            if game is not None:
                kind = "player" if role.id == game.player_role_id else "custom"
            elif role.id == Role.REGISTERED_ID:
                kind = "registered"
            elif role.id == Role.GUEST_ID:
                kind = "guest"
            else:
                kind = "site"
            here = {
                permission.value: effect.value
                for permission, effect in role_grants.get(forum.id, [])
            }
            inherited = ForumPermissions.resolve_role_verbs(role_grants, forum.heritage)
            result.append(
                (role, kind, here, {verb.value: v for verb, v in inherited.items()})
            )
        return result

    async def set_permissions(
        self,
        forum: Forum,
        entries: Sequence[tuple[int, dict[str, Effects]]],
        can_grant_moderate: bool,
    ) -> None:
        """Replace this forum's grants for each listed role with the given
        verb -> effect map, writing only the differences. Roles not listed are
        untouched."""
        role_ids = [role_id for role_id, _ in entries]
        if len(set(role_ids)) != len(role_ids):
            raise ValidationError("A role can only be listed once")
        forum_verbs = {verb.value: verb for verb in FORUM_VERBS_ORDERED}
        for _, grants in entries:
            unknown = set(grants) - forum_verbs.keys()
            if unknown:
                raise ValidationError(
                    f"Not forum permissions: {', '.join(sorted(unknown))}"
                )

        conditions = await self._eligible_conditions(forum)
        eligible = set(
            await self.db_session.scalars(
                select(Role.id).where(Role.id.in_(role_ids), *conditions)
            )
        )
        ineligible = set(role_ids) - eligible
        if ineligible:
            raise ValidationError(
                f"Roles can't be set on this forum: {sorted(ineligible)}"
            )

        existing_rows = await self.db_session.scalars(
            select(RolePermission).where(
                RolePermission.scope_type == ScopeTypes.FORUM,
                RolePermission.scope_id == forum.id,
                RolePermission.role_id.in_(role_ids),
            )
        )
        existing = {(row.role_id, row.permission): row for row in existing_rows}

        to_add: list[RolePermission] = []
        to_update: list[tuple[RolePermission, Effects]] = []
        to_delete: list[RolePermission] = []
        moderate_changed = False
        for role_id, grants in entries:
            wanted = {forum_verbs[name]: effect for name, effect in grants.items()}
            for verb, effect in wanted.items():
                row = existing.get((role_id, verb))
                if row is None:
                    to_add.append(
                        RolePermission(
                            role_id=role_id,
                            permission=verb,
                            scope_type=ScopeTypes.FORUM,
                            scope_id=forum.id,
                            effect=effect,
                        )
                    )
                elif row.effect is not effect:
                    to_update.append((row, effect))
                else:
                    continue
                moderate_changed |= verb is Verbs.FORUM_MODERATE
            for (row_role_id, verb), row in existing.items():
                if row_role_id == role_id and verb not in wanted:
                    to_delete.append(row)
                    moderate_changed |= verb is Verbs.FORUM_MODERATE

        if moderate_changed and not can_grant_moderate:
            raise ForbiddenException("Only administrators can change who moderates")

        self.db_session.add_all(to_add)
        for row, effect in to_update:
            row.effect = effect
        for row in to_delete:
            await self.db_session.delete(row)
        await self.db_session.flush()

    async def search_site_roles(self, name_filter: str | None) -> Sequence[Role]:
        """Site roles to add to a non-game forum's grid. Admin is locked and
        Registered/Guest are always listed, so they're left out."""
        query = select(Role).where(
            Role.game_role.is_(None),
            Role.id.not_in([Role.ADMIN_ID, Role.REGISTERED_ID, Role.GUEST_ID]),
        )
        if name_filter:
            query = query.where(Role._name.ilike(f"%{name_filter}%"))
        return (
            await self.db_session.scalars(
                query.order_by(Role._name).limit(ROLE_SEARCH_LIMIT)
            )
        ).all()

    async def get_game_roles(self, game: Game) -> Sequence[Role]:
        """The game's Player role, then its custom roles by name. The GM role is
        hidden."""
        return (
            await self.db_session.scalars(
                select(Role)
                .where(Role.game_role == game.id, Role.id != game.gm_role_id)
                .options(selectinload(Role.users))
                .order_by(
                    case((Role.id == game.player_role_id, 0), else_=1), Role._name
                )
            )
        ).all()

    async def get_accepted_players(self, game: Game) -> Sequence[User]:
        return (
            await self.db_session.scalars(
                select(User)
                .join(Player, Player.user_id == User.id)
                .where(
                    Player.game_id == game.id, Player.state == Player.States.ACCEPTED
                )
                .order_by(User.username)
            )
        ).all()

    async def create_game_role(self, game: Game, name: str) -> Role:
        return await RBACkRepository(self.db_session, self.principal).create_role(
            name, game.gm_id, game_id=game.id
        )

    async def get_custom_role(self, game: Game, role_id: int) -> Role:
        """One of the game's custom roles. The GM role is hidden (404); the
        Player role exists but can't be changed this way (403)."""
        role = await self.db_session.scalar(
            select(Role)
            .where(
                Role.id == role_id,
                Role.game_role == game.id,
                Role.id != game.gm_role_id,
            )
            .options(selectinload(Role.users))
        )
        if role is None:
            raise NotFoundException("Role not found")
        if role.id == game.player_role_id:
            raise ForbiddenException("The Player role can't be changed here")
        return role

    async def set_role_members(
        self, game: Game, role: Role, user_ids: Sequence[int]
    ) -> None:
        wanted = set(user_ids)
        players = {user.id: user for user in await self.get_accepted_players(game)}
        not_players = wanted - players.keys()
        if not_players:
            raise ValidationError(
                f"Not accepted players of this game: {sorted(not_players)}"
            )

        rbac_repository = RBACkRepository(self.db_session, self.principal)
        current = {member.id for member in role.users}
        for user_id in current - wanted:
            await rbac_repository.remove_user_from_role(role, user_id)
        for user_id in wanted - current:
            await rbac_repository.add_user_to_role(role, players[user_id])
