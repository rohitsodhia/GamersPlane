from collections.abc import Iterable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.models import Forum, Game, Role, RolePermission, User, UserRole

Verbs = RolePermission.ValidPermissions
Effects = RolePermission.Effects

FORUM_VERBS = frozenset(
    verb for verb in Verbs if RolePermission.ScopeTypes.FORUM in verb.allowed_scopes
)


class ForumPermissions:
    """A principal's resolved forum permissions over a fixed set of forums.

    Build with ``load()``, passing every forum you intend to check; the grants for
    each forum's whole ancestor chain are fetched in one query.

    Resolution for one verb on one forum walks the chain root -> forum (forums
    carry their ancestors in ``heritage``). At each forum, a ``deny`` beats an
    ``allow``; a more specific forum's verdict overwrites a less specific one's.
    No matching grant anywhere means deny.

    The principal's roles are their assigned roles plus one implicit role:
    Registered for a logged-in user, Guest for an anonymous request.
    ``forum_moderate`` implies every other forum verb, and holders of the global
    ``admin`` verb are allowed everything.

    A public game's root forum carries an implicit ``forum_read`` allow for
    everyone, so it behaves like a grant at that forum: it cascades into the
    game's subforums, and a deny on a subforum (or on the root itself) still wins.
    """

    def __init__(
        self,
        forum_ids: set[int],
        grants: dict[int, list[tuple[Verbs, Effects]]],
        is_admin: bool,
    ):
        self._forum_ids = forum_ids
        self._grants = grants
        self._is_admin = is_admin

    @classmethod
    async def load(
        cls,
        db_session: AsyncSession,
        principal: User | None,
        forums: Iterable[Forum],
    ) -> "ForumPermissions":
        forums = list(forums)
        forum_ids = {forum.id for forum in forums}

        is_admin = principal is not None and Verbs.ADMIN.value in (
            await principal.awaitable_attrs.global_permissions
        )
        if is_admin or not forums:
            return cls(forum_ids, {}, is_admin)

        if principal is None:
            role_filter = Role.id == Role.GUEST_ID
        else:
            role_filter = or_(
                Role.id == Role.REGISTERED_ID,
                Role.id.in_(
                    select(UserRole.role_id).where(UserRole.user_id == principal.id)
                ),
            )
        chain_ids = {
            forum_id for forum in forums for forum_id in (*forum.heritage, forum.id)
        }
        # Joining Role (rather than filtering on role_id alone) lets the
        # soft-delete criteria drop a deleted role's grants.
        rows = await db_session.execute(
            select(
                RolePermission.scope_id,
                RolePermission.permission,
                RolePermission.effect,
            )
            .join(Role)
            .where(
                RolePermission.scope_type == RolePermission.ScopeTypes.FORUM,
                RolePermission.scope_id.in_(chain_ids),
                role_filter,
            )
        )

        grants: dict[int, list[tuple[Verbs, Effects]]] = {}
        for scope_id, permission, effect in rows:
            grants.setdefault(scope_id, []).append((permission, effect))

        public_game_roots = await db_session.scalars(
            select(Game.root_forum_id).where(
                Game.root_forum_id.in_(chain_ids), Game.public.is_(True)
            )
        )
        for root_forum_id in public_game_roots:
            grants.setdefault(root_forum_id, []).append(
                (Verbs.FORUM_READ, Effects.ALLOW)
            )

        return cls(forum_ids, grants, is_admin=False)

    def has(self, forum: Forum, verb: Verbs) -> bool:
        if forum.id not in self._forum_ids:
            raise ValueError(f"Forum {forum.id} wasn't loaded into these permissions")
        if self._is_admin:
            return True

        chain = (*forum.heritage, forum.id)
        if verb is not Verbs.FORUM_MODERATE and self._resolve(
            chain, Verbs.FORUM_MODERATE
        ):
            return True
        return self._resolve(chain, verb)

    def allowed(self, forum: Forum) -> set[Verbs]:
        """Every forum verb the principal holds on this forum."""
        return {verb for verb in FORUM_VERBS if self.has(forum, verb)}

    @classmethod
    async def require_read(
        cls,
        db_session: AsyncSession,
        principal: User | None,
        forum: Forum,
        not_found: str,
    ) -> "ForumPermissions":
        """Load permissions for one forum, 404ing if the principal can't read it.

        A 404 (rather than 403) keeps private forums from confirming they exist.
        """
        permissions = await cls.load(db_session, principal, [forum])
        if not permissions.has(forum, Verbs.FORUM_READ):
            raise NotFoundException(not_found)
        return permissions

    def _resolve(self, chain: tuple[int, ...], verb: Verbs) -> bool:
        verdict = False
        for forum_id in chain:
            effects = {
                effect
                for permission, effect in self._grants.get(forum_id, ())
                if permission is verb
            }
            if Effects.DENY in effects:
                verdict = False
            elif Effects.ALLOW in effects:
                verdict = True
        return verdict
