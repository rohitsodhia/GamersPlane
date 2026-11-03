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
# Declaration order: read first, moderate last.
FORUM_VERBS_ORDERED = tuple(verb for verb in Verbs if verb in FORUM_VERBS)


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

    That's each forum one of their ``forum_moderate`` allows names, if
    ``forum_moderate`` still resolves to allow there, plus the site root for
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


async def is_site_moderator(db_session: AsyncSession, user: User) -> bool:
    """True for admins and anyone moderating at least one site (non-game) forum.

    A GM who only moderates their game's forums isn't a site moderator.
    """
    if Verbs.ADMIN.value in await user.awaitable_attrs.global_permissions:
        return True
    return any(root.game_id is None for root in await moderated_roots(db_session, user))


class ForumPermissions:
    """A principal's resolved forum permissions over a fixed set of forums.

    Build with ``load()``, passing every forum you intend to check; the grants for
    each forum's whole ancestor chain are fetched in one query.

    Grants are pooled across all of the principal's roles. For one verb on one
    forum, walk the chain from the forum up to the root (forums carry their
    ancestors in ``heritage``). The closest forum where any role has a grant for
    the verb decides: allow if any role allows there (yes wins ties), otherwise
    deny. Everything further up is ignored. No grant anywhere means deny.

    Player mode: admins and moderators of a site forum above the games also play.
    When the principal's ``moderator_mode`` is off, checks on a game forum (one
    with ``game_id``) ignore the admin bypass and any ``forum_moderate`` grant
    scoped to a chain forum outside that game, so they get what a regular member
    of their roles would. Grants on the game's own forums (a GM's moderation) and
    every other verb still count, and site forums are never affected.

    The principal's roles are their assigned roles plus one implicit role:
    Registered for a logged-in user, Guest for an anonymous request.
    ``forum_moderate`` implies every other forum verb (it resolves the same way,
    and if it resolves to allow the verb is allowed whatever it says itself), and
    holders of the global ``admin`` verb are allowed everything.

    A public game's root forum carries an implicit ``forum_read`` allow for
    everyone. It is modelled as a grant on the implicit Registered/Guest role at
    that forum, used only when that role has no explicit ``forum_read`` grant on
    the root. It cascades into the game's subforums under the normal rule, so a
    closer grant (a Registered/Guest deny on a subforum, say) overrides it.
    """

    def __init__(
        self,
        forum_ids: set[int],
        grants: dict[int, dict[int, list[tuple[Verbs, Effects]]]],
        is_admin: bool,
        chain_games: dict[int, int | None] | None = None,
    ):
        # role id -> forum id -> that role's (verb, effect) grants there
        self._forum_ids = forum_ids
        self._grants = grants
        self._is_admin = is_admin
        # Chain forum id -> its game id; only set in player mode (see class docs).
        self._chain_games = chain_games

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
        player_mode = principal is not None and not principal.moderator_mode
        # In player mode an admin's grants still matter: game forums resolve them
        # like anyone's, so only moderator-mode admins skip the grant queries.
        if (is_admin and not player_mode) or not forums:
            return cls(forum_ids, {}, is_admin)

        chain_ids = {
            forum_id for forum in forums for forum_id in (*forum.heritage, forum.id)
        }
        chain_games = None
        if player_mode:
            game_rows = await db_session.execute(
                select(Forum.id, Forum.game_id).where(Forum.id.in_(chain_ids))
            )
            chain_games = {forum_id: game_id for forum_id, game_id in game_rows}
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
        await cls._add_public_game_reads(
            db_session, grants, implicit_role_id, chain_ids
        )

        return cls(forum_ids, grants, is_admin, chain_games)

    @staticmethod
    async def _add_public_game_reads(
        db_session: AsyncSession,
        grants: dict[int, dict[int, list[tuple[Verbs, Effects]]]],
        implicit_role_id: int,
        chain_ids: set[int],
    ) -> None:
        """Add the implicit ``forum_read`` allow that a public game's root forum
        gives the implicit role, into ``grants``."""
        implicit_grants = grants.setdefault(implicit_role_id, {})

        public_game_roots = await db_session.scalars(
            select(Game.root_forum_id).where(
                Game.root_forum_id.in_(chain_ids), Game.public.is_(True)
            )
        )
        for root_forum_id in public_game_roots:
            root_grants = implicit_grants.setdefault(root_forum_id, [])
            # A fallback: an explicit read grant on the root takes precedence.
            if not any(permission is Verbs.FORUM_READ for permission, _ in root_grants):
                root_grants.append((Verbs.FORUM_READ, Effects.ALLOW))

    @classmethod
    async def load_for_users(
        cls,
        db_session: AsyncSession,
        users: Iterable[User],
        forum: Forum,
    ) -> dict[int, "ForumPermissions"]:
        """Each user's permissions on one forum (user id -> permissions), in a
        fixed handful of queries however many users there are. Results match
        ``load(db_session, user, [forum])`` for every logged-in user; there is no
        guest here.

        Queries: the users' role assignments; every role's forum grants along
        the forum's ancestor chain (narrowed per user in Python to their assigned
        roles plus Registered); the admin verb's global grants, for the admin
        check (what ``User.global_permissions`` computes, without its per-user
        lazy loads: a global deny beats an allow, over assigned plus the user's
        ``implicit_roles``); the public-game-root check; and, only if some user is
        in player mode, the chain's game ids. Player mode is honored per user
        exactly as in ``load()``.
        """
        users = list(users)
        if not users:
            return {}
        forum_ids = {forum.id}
        chain_ids = {*forum.heritage, forum.id}

        assigned: dict[int, set[int]] = {user.id: set() for user in users}
        for user_id, role_id in await db_session.execute(
            select(UserRole.user_id, UserRole.role_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id.in_(assigned))
        ):
            assigned[user_id].add(role_id)
        # Registered applies to every logged-in user (``held_by``).
        held = {user.id: assigned[user.id] | {Role.REGISTERED_ID} for user in users}
        all_role_ids = set().union(*held.values())

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
                RolePermission.role_id.in_(all_role_ids),
            )
        )
        grants: dict[int, dict[int, list[tuple[Verbs, Effects]]]] = {}
        for role_id, scope_id, permission, effect in rows:
            grants.setdefault(role_id, {}).setdefault(scope_id, []).append(
                (permission, effect)
            )
        await cls._add_public_game_reads(
            db_session, grants, Role.REGISTERED_ID, chain_ids
        )

        # The admin verb at global scope, per role, for ``global_permissions_of``.
        implicit = {user.id: {r.id for r in user.implicit_roles} for user in users}
        global_role_ids = all_role_ids.union(*implicit.values())
        admin_allowed: set[int] = set()
        admin_denied: set[int] = set()
        for role_id, effect in await db_session.execute(
            select(RolePermission.role_id, RolePermission.effect)
            .join(Role)
            .where(
                RolePermission.scope_type.is_(None),
                RolePermission.permission == Verbs.ADMIN,
                RolePermission.role_id.in_(global_role_ids),
            )
        ):
            (admin_denied if effect is Effects.DENY else admin_allowed).add(role_id)

        chain_games = None
        if any(not user.moderator_mode for user in users):
            game_rows = await db_session.execute(
                select(Forum.id, Forum.game_id).where(Forum.id.in_(chain_ids))
            )
            chain_games = {forum_id: game_id for forum_id, game_id in game_rows}

        permissions = {}
        for user in users:
            # As ``User.effective_roles``: assigned roles plus the implicit ones
            # attached to the user object (Registered only if a request set it).
            effective = assigned[user.id] | implicit[user.id]
            is_admin = bool(effective & admin_allowed) and not effective & admin_denied
            permissions[user.id] = cls(
                forum_ids,
                {
                    role_id: grants[role_id]
                    for role_id in held[user.id]
                    if role_id in grants
                },
                is_admin,
                None if user.moderator_mode else chain_games,
            )
        return permissions

    def has(self, forum: Forum, verb: Verbs) -> bool:
        if forum.id not in self._forum_ids:
            raise ValueError(f"Forum {forum.id} wasn't loaded into these permissions")
        # Player mode lifts the admin bypass inside a game's forums only.
        if self._is_admin and (self._chain_games is None or forum.game_id is None):
            return True

        chain = (*forum.heritage, forum.id)
        if verb is not Verbs.FORUM_MODERATE and self._resolve(
            chain, Verbs.FORUM_MODERATE, forum.game_id
        ):
            return True
        return self._resolve(chain, verb, forum.game_id)

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

    @classmethod
    def resolve_role_verbs(
        cls,
        role_grants: dict[int, list[tuple[Verbs, Effects]]],
        chain: Iterable[int],
    ) -> dict[Verbs, bool]:
        """What one role alone resolves to for every forum verb along ``chain``
        (forum ids, root first), with ``forum_moderate`` implying the rest."""
        chain = tuple(chain)
        if cls._resolve_role(role_grants, chain, Verbs.FORUM_MODERATE):
            return {verb: True for verb in FORUM_VERBS_ORDERED}
        return {
            verb: cls._resolve_role(role_grants, chain, verb)
            for verb in FORUM_VERBS_ORDERED
        }

    def _resolve(
        self, chain: tuple[int, ...], verb: Verbs, game_id: int | None = None
    ) -> bool:
        # Player mode in a game: moderation granted outside the game doesn't count.
        outside_game_ignored = (
            verb is Verbs.FORUM_MODERATE
            and game_id is not None
            and self._chain_games is not None
        )
        for forum_id in reversed(chain):
            if outside_game_ignored and self._chain_games.get(forum_id) != game_id:
                continue
            effects = {
                effect
                for role_grants in self._grants.values()
                for permission, effect in role_grants.get(forum_id, ())
                if permission is verb
            }
            if effects:
                return Effects.ALLOW in effects
        return False

    @staticmethod
    def _resolve_role(
        role_grants: dict[int, list[tuple[Verbs, Effects]]],
        chain: tuple[int, ...],
        verb: Verbs,
    ) -> bool:
        # A role holds at most one grant per verb and forum, so the closest
        # forum with a grant for the verb decides.
        for forum_id in reversed(chain):
            for permission, effect in role_grants.get(forum_id, ()):
                if permission is verb:
                    return effect is Effects.ALLOW
        return False
