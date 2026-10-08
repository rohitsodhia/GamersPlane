from collections.abc import Iterable

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ForbiddenException, NotFoundException
from app.models import Forum, Game, Role, RolePermission, User, UserRole
from app.repositories.forum_repository import SITE_ROOT_FORUM_ID

Verbs = RolePermission.ValidPermissions
Effects = RolePermission.Effects

FORUM_VERBS = frozenset(
    verb for verb in Verbs if RolePermission.ScopeTypes.FORUM in verb.allowed_scopes
)


def held_by(principal: User | None) -> ColumnElement[bool]:
    """Filter on ``Role`` for the roles a principal holds: their assigned roles
    plus Registered, or just Guest for an anonymous request."""
    if principal is None:
        return Role.id == Role.GUEST_ID
    return or_(
        Role.id == Role.REGISTERED_ID,
        Role.id.in_(select(UserRole.role_id).where(UserRole.user_id == principal.id)),
    )


async def moderated_roots(db_session: AsyncSession, principal: User) -> list[Forum]:
    """The forums a principal's moderation starts from.

    That's each forum one of their ``forum_moderate`` allows names, if some role
    still resolves to moderate there (the allowing role's own deny on the same
    forum beats it, but another role's deny doesn't), plus the site root for
    global admins. Moderation cascades down from these, so they
    may overlap.
    """
    granted = await db_session.scalars(
        select(Forum).where(
            Forum.id.in_(
                select(RolePermission.scope_id)
                .join(Role)
                .where(
                    RolePermission.scope_type == RolePermission.ScopeTypes.FORUM,
                    RolePermission.permission == Verbs.FORUM_MODERATE,
                    RolePermission.effect == Effects.ALLOW,
                    held_by(principal),
                )
            )
        )
    )
    roots = list(granted)
    if Verbs.ADMIN.value in await principal.awaitable_attrs.global_permissions:
        site_root = await db_session.get(Forum, SITE_ROOT_FORUM_ID)
        if site_root is not None and site_root not in roots:
            roots.append(site_root)
    permissions = await ForumPermissions.load(db_session, principal, roots)
    return [root for root in roots if permissions.has(root, Verbs.FORUM_MODERATE)]


class ForumPermissions:
    """A principal's resolved forum permissions over a fixed set of forums.

    Build with ``load()``, passing every forum you intend to check; the grants for
    each forum's whole ancestor chain are fetched in one query.

    Each role resolves independently. For one verb on one forum, a role walks the
    chain root -> forum (forums carry their ancestors in ``heritage``). At each
    forum, the role's ``deny`` beats its ``allow``; a more specific forum's
    verdict overwrites a less specific one's. No matching grant anywhere means
    deny. The principal holds the verb if any of their roles resolves to allow,
    so one role's deny never cancels another role's allow.

    The principal's roles are their assigned roles plus one implicit role:
    Registered for a logged-in user, Guest for an anonymous request.
    ``forum_moderate`` implies every other forum verb (checked per role: a role
    that moderates grants everything, whatever other roles deny), and holders of
    the global ``admin`` verb are allowed everything.

    A public game's root forum carries an implicit ``forum_read`` allow for
    everyone. It is modelled as a grant on the implicit Registered/Guest role at
    that forum: it cascades into the game's subforums, and a Registered/Guest
    deny on a subforum (or on the root itself) still wins over it.
    """

    def __init__(
        self,
        forum_ids: set[int],
        grants: dict[int, dict[int, list[tuple[Verbs, Effects]]]],
        is_admin: bool,
    ):
        # role id -> forum id -> that role's (verb, effect) grants there
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

        chain_ids = {
            forum_id for forum in forums for forum_id in (*forum.heritage, forum.id)
        }
        # Joining Role (rather than filtering on role_id alone) lets the
        # soft-delete criteria drop a deleted role's grants.
        rows = await db_session.execute(
            select(
                RolePermission.role_id,
                RolePermission.scope_id,
                RolePermission.permission,
                RolePermission.effect,
            )
            .join(Role)
            .where(
                RolePermission.scope_type == RolePermission.ScopeTypes.FORUM,
                RolePermission.scope_id.in_(chain_ids),
                held_by(principal),
            )
        )

        grants: dict[int, dict[int, list[tuple[Verbs, Effects]]]] = {}
        for role_id, scope_id, permission, effect in rows:
            grants.setdefault(role_id, {}).setdefault(scope_id, []).append(
                (permission, effect)
            )

        implicit_role_id = Role.GUEST_ID if principal is None else Role.REGISTERED_ID
        implicit_grants = grants.setdefault(implicit_role_id, {})

        public_game_roots = await db_session.scalars(
            select(Game.root_forum_id).where(
                Game.root_forum_id.in_(chain_ids), Game.public.is_(True)
            )
        )
        for root_forum_id in public_game_roots:
            implicit_grants.setdefault(root_forum_id, []).append(
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

    @classmethod
    async def require_moderate(
        cls, db_session: AsyncSession, principal: User, forum: Forum
    ) -> None:
        """403 unless the principal moderates the forum; 404 if they can't even
        read it, as in ``require_read``."""
        permissions = await cls.load(db_session, principal, [forum])
        if permissions.has(forum, Verbs.FORUM_MODERATE):
            return
        if not permissions.has(forum, Verbs.FORUM_READ):
            raise NotFoundException("Forum not found")
        raise ForbiddenException("You can't moderate this forum")

    def _resolve(self, chain: tuple[int, ...], verb: Verbs) -> bool:
        return any(
            self._resolve_role(role_grants, chain, verb)
            for role_grants in self._grants.values()
        )

    @staticmethod
    def _resolve_role(
        role_grants: dict[int, list[tuple[Verbs, Effects]]],
        chain: tuple[int, ...],
        verb: Verbs,
    ) -> bool:
        verdict = False
        for forum_id in chain:
            effects = {
                effect
                for permission, effect in role_grants.get(forum_id, ())
                if permission is verb
            }
            if Effects.DENY in effects:
                verdict = False
            elif Effects.ALLOW in effects:
                verdict = True
        return verdict
