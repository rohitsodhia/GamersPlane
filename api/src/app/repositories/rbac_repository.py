from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import ConflictException, NotFoundException, ValidationError
from app.models import Forum, Game, Role, RolePermission, User


class RBACkRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    def get_permissions(self):
        return [
            {
                "value": permission.value,
                "label": permission.label,
            }
            for permission in RolePermission.ValidPermissions
        ]

    def _manageable_role_ids(self) -> set[int]:
        """Role ids the principal can administer via a scoped ``role_admin`` grant.

        Walks the roles/grants already eager-loaded onto the principal by the auth
        middleware (via ``User.global_permissions``), so it issues no extra IO.
        A scoped ``deny`` beats a scoped ``allow`` for the same role.
        """
        verb = RolePermission.ValidPermissions.ROLE_ADMIN.value
        allowed: set[int] = set()
        denied: set[int] = set()
        for role in self.principal.roles:
            for grant in role.grants:
                if (
                    grant.permission.value != verb
                    or grant.scope_type is not RolePermission.ScopeTypes.ROLE
                ):
                    continue
                if grant.effect is RolePermission.Effects.DENY:
                    denied.add(grant.scope_id)
                else:
                    allowed.add(grant.scope_id)
        return allowed - denied

    def can_manage_role(self, role_id: int) -> bool:
        """True if the principal may administer this role.

        Global ``admin`` holders can manage every role; everyone else needs a
        scoped ``role_admin`` grant for this specific role.
        """
        if self.principal.has_global_permission(
            RolePermission.ValidPermissions.ADMIN.value
        ):
            return True
        return role_id in self._manageable_role_ids()

    async def get_roles(self, name_filter: str | None = None) -> Sequence[Role]:
        """Roles visible to the principal.

        Holders of the global ``admin`` verb get every role; everyone else gets
        only the roles they hold a scoped ``role_admin`` grant for.
        """
        query = select(Role).options(
            selectinload(Role.owner),
            selectinload(Role.grants),
            selectinload(Role.users),
        )
        if name_filter:
            query = query.where(Role._name.ilike(f"%{name_filter}%"))
        if not self.principal.has_global_permission(
            RolePermission.ValidPermissions.ADMIN.value
        ):
            query = query.where(Role.id.in_(self._manageable_role_ids()))

        return (await self.db_session.execute(query)).scalars().all()

    async def get_role(self, role_id: int) -> Role | None:
        query = (
            select(Role)
            .where(Role.id == role_id)
            .options(
                selectinload(Role.owner),
                selectinload(Role.users),
                selectinload(Role.grants),
            )
        )
        return (await self.db_session.execute(query)).scalar_one_or_none()

    async def get_scope_names(
        self, grants: Sequence[RolePermission]
    ) -> dict[tuple[RolePermission.ScopeTypes, int], str]:
        """Resolve the scoped resource each grant points at to its display name.

        Batched into one query per scope type. Keys are ``(scope_type, scope_id)``;
        global grants (no scope) contribute nothing.
        """
        forum_ids = {
            grant.scope_id
            for grant in grants
            if grant.scope_type is RolePermission.ScopeTypes.FORUM
        }
        role_ids = {
            grant.scope_id
            for grant in grants
            if grant.scope_type is RolePermission.ScopeTypes.ROLE
        }

        names: dict[tuple[RolePermission.ScopeTypes, int], str] = {}
        if forum_ids:
            rows = await self.db_session.execute(
                select(Forum.id, Forum.title).where(Forum.id.in_(forum_ids))
            )
            for forum_id, title in rows:
                names[(RolePermission.ScopeTypes.FORUM, forum_id)] = title
        if role_ids:
            rows = await self.db_session.execute(
                select(Role.id, Role._name).where(Role.id.in_(role_ids))
            )
            for role_id, name in rows:
                names[(RolePermission.ScopeTypes.ROLE, role_id)] = name
        return names

    async def create_role(self, name: str, owner_id: int) -> Role:
        """Create a role. The plural is derived from the name by the model."""
        role = Role(owner_id=owner_id)
        role.name = name
        self.db_session.add(role)
        try:
            await self.db_session.flush()
        except IntegrityError as exc:
            raise ConflictException("A role with that name already exists") from exc
        return role

    async def update_role(
        self,
        role: Role,
        name: str | None = None,
        owner: User | None = None,
    ) -> Role:
        """Apply a partial update. ``None`` means "leave this field alone"."""
        if name is not None:
            role.name = name
        if owner is not None:
            role.owner = owner
        try:
            await self.db_session.flush()
        except IntegrityError as exc:
            raise ConflictException("A role with that name already exists") from exc
        return role

    async def _require_scope_target(
        self, model: type, target_id: int, label: str
    ) -> None:
        found = await self.db_session.execute(
            select(model.id).where(model.id == target_id)
        )
        if found.scalar_one_or_none() is None:
            raise NotFoundException(f"{label} not found")

    async def create_grant(
        self,
        role: Role,
        permission: RolePermission.ValidPermissions,
        scope_type: RolePermission.ScopeTypes | None = None,
        scope_id: int | None = None,
        effect: RolePermission.Effects = RolePermission.Effects.ALLOW,
    ) -> RolePermission:
        if not permission.scope_allowed(scope_type):
            scope_label = scope_type.value if scope_type else "global"
            raise ValidationError(
                f"{permission.label} cannot be granted at {scope_label} scope"
            )

        if scope_type is RolePermission.ScopeTypes.FORUM:
            await self._require_scope_target(Forum, scope_id, "Forum")
        elif scope_type is RolePermission.ScopeTypes.ROLE:
            await self._require_scope_target(Role, scope_id, "Role")

        grant = role.grant(
            permission, scope_type=scope_type, scope_id=scope_id, effect=effect
        )
        try:
            await self.db_session.flush()
        except IntegrityError as exc:
            raise ConflictException("That grant already exists on this role") from exc
        return grant

    def get_grant(self, role: Role, grant_id: int) -> RolePermission | None:
        """Find one of this role's grants by id (grants are already loaded)."""
        return next((g for g in role.grants if g.id == grant_id), None)

    async def update_grant(
        self, grant: RolePermission, effect: RolePermission.Effects
    ) -> RolePermission:
        grant.effect = effect
        await self.db_session.flush()
        return grant

    async def delete_grant(self, role: Role, grant: RolePermission) -> None:
        """Hard-delete a grant row.

        Removing it from ``role.grants`` (delete-orphan cascade) rather than a
        bare ``session.delete`` keeps the in-memory collection consistent, so a
        later read in the same session can't resurrect it.
        """
        role.grants.remove(grant)
        await self.db_session.flush()

    async def add_user_to_role(self, role: Role, user: User) -> None:
        """Idempotent: no-op if the user already holds the role."""
        if any(member.id == user.id for member in role.users):
            return
        role.users.append(user)
        await self.db_session.flush()

    async def remove_user_from_role(self, role: Role, user_id: int) -> None:
        """Idempotent: no-op if the user isn't in the role."""
        member = next((m for m in role.users if m.id == user_id), None)
        if member is None:
            return
        role.users.remove(member)
        await self.db_session.flush()

    async def delete_role(self, role: Role) -> None:
        """Soft-delete a role. Refuses if the role is a game's primary role."""
        backing_game = await self.db_session.execute(
            select(Game.id).where(Game.role_id == role.id).limit(1)
        )
        if backing_game.scalar_one_or_none() is not None:
            raise ConflictException("This role backs a game and can't be deleted")
        role.deleted = datetime.now(UTC)
        await self.db_session.flush()
