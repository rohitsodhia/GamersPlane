"""``ForumPermissions.load_for_users`` must agree with ``load`` for every verb."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.forums.permissions import FORUM_VERBS, ForumPermissions
from app.models import Game, Role, RolePermission
from tests.factories import (
    ActivatedUserFactory,
    ForumFactory,
    RoleFactory,
    SystemFactory,
)

Verbs = RolePermission.ValidPermissions
Scopes = RolePermission.ScopeTypes
Effects = RolePermission.Effects


@pytest.fixture(autouse=True)
async def _isolate(wrap_in_savepoint):
    pass


@pytest.fixture
async def forums(create):
    """A root -> parent -> child chain, linked through ``heritage``."""
    root = await create(ForumFactory, heritage=[])
    parent = await create(ForumFactory, parent_id=root.id, heritage=[root.id])
    child = await create(
        ForumFactory, parent_id=parent.id, heritage=[root.id, parent.id]
    )
    return root, parent, child


@pytest.fixture
def new_user(create):
    async def _new_user():
        return await create(ActivatedUserFactory)

    return _new_user


@pytest.fixture
def make_role(db_session):
    async def _make_role(*grants, members=()):
        """Build a role holding ``(verb, forum, effect)`` grants."""
        role = RoleFactory.build()
        db_session.add(role)
        for verb, forum, effect in grants:
            role.grant(
                verb,
                scope_type=None if forum is None else Scopes.FORUM,
                scope_id=None if forum is None else forum.id,
                effect=effect,
            )
        for member in members:
            role.users.append(member)
        await db_session.flush()
        return role

    return _make_role


@pytest.fixture
def implicit_roles(monkeypatch, make_role):
    async def _implicit_roles(*, registered=()):
        registered_role = await make_role(*registered)
        guest_role = await make_role()
        monkeypatch.setattr(Role, "REGISTERED_ID", registered_role.id)
        monkeypatch.setattr(Role, "GUEST_ID", guest_role.id)

    return _implicit_roles


async def assert_parity(db_session, users, forum):
    """Bulk and single loading agree on every verb; returns the bulk result."""
    bulk = await ForumPermissions.load_for_users(db_session, users, forum)
    assert set(bulk) == {user.id for user in users}
    for user in users:
        single = await ForumPermissions.load(db_session, user, [forum])
        for verb in FORUM_VERBS:
            assert bulk[user.id].has(forum, verb) == single.has(forum, verb), (
                user.id,
                verb,
            )
    return bulk


class TestParity:
    async def test_empty_users_list(self, db_session, forums):
        assert await ForumPermissions.load_for_users(db_session, [], forums[0]) == {}

    async def test_registered_grant_and_no_grants(
        self, db_session, forums, new_user, implicit_roles
    ):
        root, _, child = forums
        await implicit_roles(registered=[(Verbs.FORUM_READ, root, Effects.ALLOW)])
        users = [await new_user(), await new_user()]

        bulk = await assert_parity(db_session, users, child)

        assert bulk[users[0].id].has(child, Verbs.FORUM_READ)
        assert not bulk[users[0].id].has(child, Verbs.FORUM_WRITE)

    async def test_nothing_granted_denies_everything(
        self, db_session, forums, new_user, implicit_roles
    ):
        await implicit_roles()
        user = await new_user()

        bulk = await assert_parity(db_session, [user], forums[0])

        assert bulk[user.id].allowed(forums[0]) == set()

    async def test_assigned_role_only_reaches_its_members(
        self, db_session, forums, new_user, make_role, implicit_roles
    ):
        await implicit_roles()
        root, _, child = forums
        member, outsider = await new_user(), await new_user()
        await make_role((Verbs.FORUM_READ, root, Effects.ALLOW), members=[member])

        bulk = await assert_parity(db_session, [member, outsider], child)

        assert bulk[member.id].has(child, Verbs.FORUM_READ)
        assert not bulk[outsider.id].has(child, Verbs.FORUM_READ)

    async def test_subforum_deny_overrides_ancestor_allow(
        self, db_session, forums, new_user, make_role, implicit_roles
    ):
        await implicit_roles()
        root, _, child = forums
        user = await new_user()
        await make_role(
            (Verbs.FORUM_READ, root, Effects.ALLOW),
            (Verbs.FORUM_READ, child, Effects.DENY),
            members=[user],
        )

        bulk = await assert_parity(db_session, [user], child)

        assert not bulk[user.id].has(child, Verbs.FORUM_READ)

    async def test_allow_in_one_role_beats_deny_in_another(
        self, db_session, forums, new_user, make_role, implicit_roles
    ):
        await implicit_roles()
        root, _, _ = forums
        user = await new_user()
        await make_role((Verbs.FORUM_WRITE, root, Effects.DENY), members=[user])
        await make_role((Verbs.FORUM_WRITE, root, Effects.ALLOW), members=[user])

        bulk = await assert_parity(db_session, [user], root)

        assert bulk[user.id].has(root, Verbs.FORUM_WRITE)

    async def test_deleted_role_grants_are_ignored(
        self, db_session, forums, new_user, make_role, implicit_roles
    ):
        await implicit_roles()
        root, _, _ = forums
        user = await new_user()
        role = await make_role((Verbs.FORUM_WRITE, root, Effects.ALLOW), members=[user])
        role.deleted = datetime.now(UTC)
        await db_session.flush()

        bulk = await assert_parity(db_session, [user], root)

        assert not bulk[user.id].has(root, Verbs.FORUM_WRITE)

    async def test_moderate_implies_other_verbs(
        self, db_session, forums, new_user, make_role, implicit_roles
    ):
        await implicit_roles()
        root, _, child = forums
        user = await new_user()
        await make_role((Verbs.FORUM_MODERATE, root, Effects.ALLOW), members=[user])

        bulk = await assert_parity(db_session, [user], child)

        assert bulk[user.id].allowed(child) == FORUM_VERBS

    async def test_global_admin_and_global_deny_overriding_it(
        self, db_session, forums, new_user, make_role, implicit_roles
    ):
        await implicit_roles()
        _, _, child = forums
        admin, blocked_admin, plain = (
            await new_user(),
            await new_user(),
            await new_user(),
        )
        await make_role((Verbs.ADMIN, None, Effects.ALLOW), members=[admin])
        await make_role((Verbs.ADMIN, None, Effects.ALLOW), members=[blocked_admin])
        await make_role((Verbs.ADMIN, None, Effects.DENY), members=[blocked_admin])

        bulk = await assert_parity(db_session, [admin, blocked_admin, plain], child)

        assert bulk[admin.id].allowed(child) == FORUM_VERBS
        assert bulk[blocked_admin.id].allowed(child) == set()


class TestPublicGames:
    @pytest.fixture
    async def make_game(self, create, db_session):
        system = await create(SystemFactory)
        gm = await create(ActivatedUserFactory)
        games_root = await create(ForumFactory, heritage=[])

        async def _make_game(*, public):
            forum = await create(
                ForumFactory, parent_id=games_root.id, heritage=[games_root.id]
            )
            game = Game(
                title="Game",
                system=system,
                gm=gm,
                post_frequency="1/d",
                num_players=4,
                root_forum=forum,
                gm_role=RoleFactory.build(owner=gm),
                player_role=RoleFactory.build(owner=gm),
                public=public,
            )
            db_session.add(game)
            await db_session.flush()
            forum.game_id = game.id
            subforum = await create(
                ForumFactory,
                parent_id=forum.id,
                heritage=[games_root.id, forum.id],
                game_id=game.id,
            )
            return games_root, forum, subforum

        return _make_game

    async def test_public_root_is_readable_and_a_registered_deny_on_a_subforum_wins(
        self, db_session, new_user, make_game, implicit_roles
    ):
        _, root, subforum = await make_game(public=True)
        await implicit_roles(registered=[(Verbs.FORUM_READ, subforum, Effects.DENY)])
        user = await new_user()

        on_root = await assert_parity(db_session, [user], root)
        on_sub = await assert_parity(db_session, [user], subforum)

        assert on_root[user.id].has(root, Verbs.FORUM_READ)
        assert not on_sub[user.id].has(subforum, Verbs.FORUM_READ)

    async def test_private_game_is_not_readable(
        self, db_session, new_user, make_game, implicit_roles
    ):
        await implicit_roles()
        _, root, _ = await make_game(public=False)
        user = await new_user()

        bulk = await assert_parity(db_session, [user], root)

        assert not bulk[user.id].has(root, Verbs.FORUM_READ)

    async def test_player_mode_users_get_the_same_as_load(
        self, db_session, new_user, make_game, make_role, implicit_roles
    ):
        await implicit_roles()
        games_root, root, subforum = await make_game(public=True)
        outside_moderator, admin, gm_like = (
            await new_user(),
            await new_user(),
            await new_user(),
        )
        outside_scope = SimpleNamespace(id=games_root.id)
        await make_role(
            (Verbs.FORUM_MODERATE, outside_scope, Effects.ALLOW),
            members=[outside_moderator],
        )
        await make_role((Verbs.ADMIN, None, Effects.ALLOW), members=[admin])
        await make_role((Verbs.FORUM_MODERATE, root, Effects.ALLOW), members=[gm_like])
        moderator_mode_user = await new_user()
        await make_role(
            (Verbs.FORUM_MODERATE, outside_scope, Effects.ALLOW),
            members=[moderator_mode_user],
        )
        users = [outside_moderator, admin, gm_like, moderator_mode_user]
        for user in users[:3]:
            user.moderator_mode = False

        bulk = await assert_parity(db_session, users, subforum)

        assert not bulk[outside_moderator.id].has(subforum, Verbs.FORUM_MODERATE)
        assert bulk[gm_like.id].has(subforum, Verbs.FORUM_MODERATE)
        # Same grant, but not in player mode, so it still moderates the game.
        assert bulk[moderator_mode_user.id].has(subforum, Verbs.FORUM_MODERATE)


class TestImplicitRolesOnTheUser:
    async def test_request_attached_registered_role_counts_for_admin(
        self, db_session, forums, new_user, make_role, implicit_roles
    ):
        """``User.effective_roles`` includes the implicit roles a request attaches,
        so a global admin grant (or deny) on Registered applies."""
        root, _, _ = forums
        await implicit_roles(registered=[(Verbs.ADMIN, None, Effects.ALLOW)])
        registered = await db_session.get(Role, Role.REGISTERED_ID)
        attached, detached, denied = (
            await new_user(),
            await new_user(),
            await new_user(),
        )
        attached.implicit_roles = (registered,)
        denied.implicit_roles = (registered,)
        await make_role((Verbs.ADMIN, None, Effects.DENY), members=[denied])

        bulk = await assert_parity(db_session, [attached, detached, denied], root)

        assert bulk[attached.id].allowed(root) == FORUM_VERBS
        assert bulk[detached.id].allowed(root) == set()
        assert bulk[denied.id].allowed(root) == set()
