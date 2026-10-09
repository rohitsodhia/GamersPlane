from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationError,
)
from app.forums.permissions import is_site_moderator
from app.models import Forum, Game, Role, RolePermission, User, UserRole

# Role #1 is the bootstrap "site owner" role and user #1 its permanent member.
# Both are hard-locked below so no API caller can rename, delete, re-own, or
# re-grant the role, or drop the primary account out of it — the goal is that
# the primary user can never be locked out, even by another admin.
PROTECTED_ROLE_ID = Role.ADMIN_ID
PROTECTED_ROLE_MEMBER_ID = 1
# Registered/Guest membership is implicit, so they can't be deleted and their
# member lists can't be edited. Their names, owners and grants stay editable —
# grants on them are how site-wide forum defaults are set.
IMPLICIT_ROLE_IDS = frozenset({Role.REGISTERED_ID, Role.GUEST_ID})
# A game's GM role is fixed (moderate on the game's forum, set at creation), and
# both the GM and Player roles take their members from the game's player list.
GM_GRANTS_LOCKED = "A game's GM role's grants can't be changed"


class RBACkRepository:
    def __init__(self, db_session: AsyncSession, principal: User):
        self.db_session = db_session
        self.principal = principal

    async def _game_role_kind(self, role_id: int) -> str | None:
        """``"gm"`` or ``"player"`` if the role is a game's GM or Player role."""
        row = (
            await self.db_session.execute(
                select(Game.gm_role_id, Game.player_role_id)
                .where(or_(Game.gm_role_id == role_id, Game.player_role_id == role_id))
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return "gm" if row.gm_role_id == role_id else "player"

    async def _require_not_gm_role(self, role_id: int, message: str) -> None:
        if await self._game_role_kind(role_id) == "gm":
            raise ForbiddenException(message)

    async def _require_members_unmanaged(self, role_id: int) -> None:
        if await self._game_role_kind(role_id) is not None:
            raise ForbiddenException("This role's members are managed by its game")

    def get_permissions(self):
        return [
            {
                "value": permission.value,
                "label": permission.label,
                "scopes": sorted(
                    "global" if scope is None else scope.value
                    for scope in permission.allowed_scopes
                ),
            }
            for permission in RolePermission.ValidPermissions
            if permission.api_grantable
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
        for role in self.principal.effective_roles:
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

    def is_admin(self) -> bool:
        return self.principal.has_global_permission(
            RolePermission.ValidPermissions.ADMIN.value
        )

    def _owns_site_role(self, role: Role) -> bool:
        return role.game_role is None and role.owner_id == self.principal.id

    def can_view_role(self, role: Role) -> bool:
        """True if the principal can see this role at all.

        Admins see everything; others see roles they hold a scoped ``role_admin``
        grant for, plus the site roles they own.
        """
        return (
            self.is_admin()
            or role.id in self._manageable_role_ids()
            or self._owns_site_role(role)
        )

    def _is_locked_role(self, role: Role) -> bool:
        """The Admin role and the implicit Registered/Guest roles are admin-only."""
        return role.id == PROTECTED_ROLE_ID or role.id in IMPLICIT_ROLE_IDS

    def can_edit_role(self, role: Role) -> bool:
        """Rename a role and add/remove its members.

        Admins always (the per-action guards still apply); others only on an
        unlocked site role they own or hold a scoped ``role_admin`` grant for.
        """
        if self.is_admin():
            return True
        if role.game_role is not None or self._is_locked_role(role):
            return False
        return self._owns_site_role(role) or role.id in self._manageable_role_ids()

    def can_delete_role(self, role: Role) -> bool:
        """Admins, or the owner of an unlocked site role (not ``role_admin``)."""
        if self.is_admin():
            return True
        return self._owns_site_role(role) and not self._is_locked_role(role)

    async def get_managers(self, role_id: int) -> Sequence[Role]:
        """Roles holding an allowing scoped ``role_admin`` grant on this role."""
        return (
            (
                await self.db_session.execute(
                    select(Role)
                    .join(RolePermission, RolePermission.role_id == Role.id)
                    .where(
                        RolePermission.permission
                        == RolePermission.ValidPermissions.ROLE_ADMIN,
                        RolePermission.scope_type == RolePermission.ScopeTypes.ROLE,
                        RolePermission.scope_id == role_id,
                        RolePermission.effect == RolePermission.Effects.ALLOW,
                    )
                    .order_by(Role._name)
                )
            )
            .scalars()
            .all()
        )

    async def has_role_admin(self) -> bool:
        """True if the principal administers or owns any role, or is a site
        moderator (who can create roles). Gates the Roles ACP page."""
        if self.is_admin() or self._manageable_role_ids():
            return True
        owned = await self.db_session.execute(
            select(Role.id)
            .where(Role.owner_id == self.principal.id, Role.game_role.is_(None))
            .limit(1)
        )
        if owned.scalar_one_or_none() is not None:
            return True
        return await is_site_moderator(self.db_session, self.principal)

    async def _site_moderator_ids(self, user_ids: Iterable[int]) -> set[int]:
        """Which of these users are site moderators right now."""
        user_ids = set(user_ids)
        if not user_ids:
            return set()
        users = await self.db_session.scalars(select(User).where(User.id.in_(user_ids)))
        return {
            user.id for user in users if await is_site_moderator(self.db_session, user)
        }

    async def moderators_among_members(self, role_ids: Iterable[int]) -> set[int]:
        """Site moderators among the roles' explicit members. Registered/Guest
        membership is implicit, so those roles are skipped."""
        role_ids = {role_id for role_id in role_ids if role_id not in IMPLICIT_ROLE_IDS}
        if not role_ids:
            return set()
        member_ids = await self.db_session.scalars(
            select(UserRole.user_id).where(UserRole.role_id.in_(role_ids))
        )
        return await self._site_moderator_ids(member_ids)

    async def _confers_moderation(self, role_id: int) -> bool:
        """True if the role holds an allowing ``forum_moderate`` or ``admin``
        grant, i.e. if belonging to it could make someone a moderator."""
        found = await self.db_session.scalar(
            select(RolePermission.id)
            .where(
                RolePermission.role_id == role_id,
                RolePermission.effect == RolePermission.Effects.ALLOW,
                or_(
                    RolePermission.permission
                    == RolePermission.ValidPermissions.FORUM_MODERATE,
                    RolePermission.permission == RolePermission.ValidPermissions.ADMIN,
                ),
            )
            .limit(1)
        )
        return found is not None

    async def release_lapsed_moderators(self, before: set[int]) -> None:
        """Hand the site roles of users who were site moderators (``before``, as
        captured ahead of a change and flushed since) but no longer are to the
        fallback owner."""
        if not before:
            return
        still = await self._site_moderator_ids(before)
        await self.release_orphaned_roles(before - still)

    async def release_orphaned_roles(self, user_ids: Iterable[int]) -> None:
        """Move the unlocked site roles these users own to the fallback owner."""
        user_ids = set(user_ids)
        if not user_ids:
            return
        roles = await self.db_session.scalars(
            select(Role).where(
                Role.owner_id.in_(user_ids),
                Role.game_role.is_(None),
                Role.id.not_in({PROTECTED_ROLE_ID, *IMPLICIT_ROLE_IDS}),
            )
        )
        for role in roles:
            role.owner_id = User.FALLBACK_OWNER_ID
            # The loaded owner would otherwise keep pointing at the old user.
            self.db_session.expire(role, ["owner"])
        await self.db_session.flush()

    async def get_roles(
        self, name_filter: str | None = None, game_roles: bool = False
    ) -> Sequence[Role]:
        """Roles visible to the principal.

        Holders of the global ``admin`` verb get every role; everyone else gets
        the roles they hold a scoped ``role_admin`` grant for, plus the site
        roles they own.
        """
        query = select(Role).options(
            selectinload(Role.owner),
            selectinload(Role.grants),
            selectinload(Role.users),
        )
        if name_filter:
            query = query.where(Role._name.ilike(f"%{name_filter}%"))
        if game_roles:
            query = query.where(Role.game_role.is_not(None))
        else:
            query = query.where(Role.game_role.is_(None))
        if not self.is_admin():
            visible = Role.id.in_(self._manageable_role_ids())
            if not game_roles:
                # Owners see their own site roles (the query is already site-only).
                visible = or_(visible, Role.owner_id == self.principal.id)
            query = query.where(visible)

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

    async def create_role(
        self, name: str, owner_id: int, game_id: int | None = None
    ) -> Role:
        """Create a role. The plural is derived from the name by the model."""
        role = Role(owner_id=owner_id, game_role=game_id)
        role.name = name
        try:
            # A savepoint, so a name collision leaves the session usable.
            async with self.db_session.begin_nested():
                self.db_session.add(role)
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
        if role.id == PROTECTED_ROLE_ID:
            raise ForbiddenException("This role is protected and can't be edited")
        if name is not None:
            await self._require_not_gm_role(
                role.id, "A game's GM role can't be renamed"
            )
        try:
            # A savepoint, so a name collision leaves the session usable (and the
            # role unchanged).
            async with self.db_session.begin_nested():
                if name is not None:
                    role.name = name
                if owner is not None:
                    role.owner = owner
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
        if role.id == PROTECTED_ROLE_ID:
            raise ForbiddenException(
                "This role is protected and its grants can't be changed"
            )
        await self._require_not_gm_role(role.id, GM_GRANTS_LOCKED)
        if not permission.scope_allowed(scope_type):
            scope_label = scope_type.value if scope_type else "global"
            raise ValidationError(
                f"{permission.label} cannot be granted at {scope_label} scope"
            )
        if not permission.api_grantable:
            raise ValidationError(f"{permission.label} cannot be granted via API")

        if scope_type is RolePermission.ScopeTypes.FORUM:
            await self._require_scope_target(Forum, scope_id, "Forum")
        elif scope_type is RolePermission.ScopeTypes.ROLE:
            await self._require_scope_target(Role, scope_id, "Role")

        # No release hook: a new grant can't end anyone's moderation, since a
        # role's deny only beats its own allow on the same forum, and that pair
        # would be the grant this one collides with.
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
        if grant.role_id == PROTECTED_ROLE_ID:
            raise ForbiddenException(
                "This role is protected and its grants can't be changed"
            )
        await self._require_not_gm_role(grant.role_id, GM_GRANTS_LOCKED)
        before = await self._moderators_if_moderate(grant)
        grant.effect = effect
        await self.db_session.flush()
        await self.release_lapsed_moderators(before)
        return grant

    async def _moderators_if_moderate(self, grant: RolePermission) -> set[int]:
        """Site moderators among the grant's role's members, but only when the
        grant is a ``forum_moderate`` (the only verb that can end moderation)."""
        if grant.permission not in (
            RolePermission.ValidPermissions.FORUM_MODERATE,
            RolePermission.ValidPermissions.ADMIN,
        ):
            return set()
        return await self.moderators_among_members([grant.role_id])

    async def delete_grant(self, role: Role, grant: RolePermission) -> None:
        """Hard-delete a grant row.

        Removing it from ``role.grants`` (delete-orphan cascade) rather than a
        bare ``session.delete`` keeps the in-memory collection consistent, so a
        later read in the same session can't resurrect it.
        """
        if role.id == PROTECTED_ROLE_ID:
            raise ForbiddenException(
                "This role is protected and its grants can't be changed"
            )
        await self._require_not_gm_role(role.id, GM_GRANTS_LOCKED)
        before = await self._moderators_if_moderate(grant)
        role.grants.remove(grant)
        await self.db_session.flush()
        await self.release_lapsed_moderators(before)

    async def add_user_to_role(self, role: Role, user: User) -> None:
        """Idempotent: no-op if the user already holds the role."""
        if role.id in IMPLICIT_ROLE_IDS:
            raise ForbiddenException("Membership in this role is automatic")
        await self._require_members_unmanaged(role.id)
        if any(member.id == user.id for member in role.users):
            return
        role.users.append(user)
        await self.db_session.flush()

    async def remove_user_from_role(self, role: Role, user_id: int) -> None:
        """Idempotent: no-op if the user isn't in the role."""
        if role.id in IMPLICIT_ROLE_IDS:
            raise ForbiddenException("Membership in this role is automatic")
        if role.id == PROTECTED_ROLE_ID and user_id == PROTECTED_ROLE_MEMBER_ID:
            raise ForbiddenException("This user can't be removed from this role")
        await self._require_members_unmanaged(role.id)
        member = next((m for m in role.users if m.id == user_id), None)
        if member is None:
            return
        before = (
            await self._site_moderator_ids([user_id])
            if await self._confers_moderation(role.id)
            else set()
        )
        role.users.remove(member)
        await self.db_session.flush()
        await self.release_lapsed_moderators(before)

    async def delete_role(self, role: Role) -> None:
        """Soft-delete a role. Refuses if the role is a game's GM or player role."""
        if role.id == PROTECTED_ROLE_ID or role.id in IMPLICIT_ROLE_IDS:
            raise ForbiddenException("This role is protected and can't be deleted")
        backing_game = await self.db_session.execute(
            select(Game.id)
            .where(or_(Game.gm_role_id == role.id, Game.player_role_id == role.id))
            .limit(1)
        )
        if backing_game.scalar_one_or_none() is not None:
            raise ConflictException("This role backs a game and can't be deleted")
        before = (
            await self.moderators_among_members([role.id])
            if await self._confers_moderation(role.id)
            else set()
        )
        role.deleted = datetime.now(UTC)
        await self.db_session.flush()
        await self.release_lapsed_moderators(before)
