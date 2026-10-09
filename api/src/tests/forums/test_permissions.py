from datetime import UTC, datetime

import pytest

from app.forums.permissions import FORUM_VERBS, ForumPermissions, moderated_roots
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
async def user(create):
    return await create(ActivatedUserFactory)


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
    """Build stand-ins for Registered/Guest and point ``Role``'s ids at them.

    Forcing the real ids 2/3 past the shared sequence isn't practical, so the
    class constants are repointed for the test instead.
    """

    async def _implicit_roles(*, registered=(), guest=()):
        registered_role = await make_role(*registered)
        guest_role = await make_role(*guest)
        monkeypatch.setattr(Role, "REGISTERED_ID", registered_role.id)
        monkeypatch.setattr(Role, "GUEST_ID", guest_role.id)

    return _implicit_roles


async def check(db_session, principal, forum, verb):
    permissions = await ForumPermissions.load(db_session, principal, [forum])
    return permissions.has(forum, verb)


class TestImplicitRoles:
    async def test_no_grants_denies(self, db_session, forums, user, implicit_roles):
        await implicit_roles()
        root, _, _ = forums

        assert not await check(db_session, user, root, Verbs.FORUM_READ)
        assert not await check(db_session, None, root, Verbs.FORUM_READ)

    async def test_guest_grants_apply_only_to_anonymous_requests(
        self, db_session, forums, user, implicit_roles
    ):
        root, _, _ = forums
        await implicit_roles(guest=[(Verbs.FORUM_READ, root, Effects.ALLOW)])

        assert await check(db_session, None, root, Verbs.FORUM_READ)
        assert not await check(db_session, user, root, Verbs.FORUM_READ)

    async def test_registered_grants_apply_only_to_logged_in_users(
        self, db_session, forums, user, implicit_roles
    ):
        root, _, _ = forums
        await implicit_roles(registered=[(Verbs.FORUM_READ, root, Effects.ALLOW)])

        assert await check(db_session, user, root, Verbs.FORUM_READ)
        assert not await check(db_session, None, root, Verbs.FORUM_READ)


class TestAssignedRoles:
    async def test_assigned_role_grants_apply(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        await implicit_roles()
        root, _, _ = forums
        await make_role((Verbs.FORUM_WRITE, root, Effects.ALLOW), members=[user])

        assert await check(db_session, user, root, Verbs.FORUM_WRITE)

    async def test_unassigned_role_grants_do_not_apply(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        await implicit_roles()
        root, _, _ = forums
        await make_role((Verbs.FORUM_WRITE, root, Effects.ALLOW))

        assert not await check(db_session, user, root, Verbs.FORUM_WRITE)

    async def test_deleted_role_grants_are_ignored(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        await implicit_roles()
        root, _, _ = forums
        role = await make_role((Verbs.FORUM_WRITE, root, Effects.ALLOW), members=[user])
        role.deleted = datetime.now(UTC)
        await db_session.flush()

        assert not await check(db_session, user, root, Verbs.FORUM_WRITE)

    async def test_global_admin_is_allowed_everything(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        await implicit_roles()
        _, _, child = forums
        await make_role((Verbs.ADMIN, None, Effects.ALLOW), members=[user])

        permissions = await ForumPermissions.load(db_session, user, [child])

        assert permissions.allowed(child) == FORUM_VERBS


class TestResolution:
    async def test_ancestor_grant_cascades_down(
        self, db_session, forums, user, implicit_roles
    ):
        root, _, child = forums
        await implicit_roles(registered=[(Verbs.FORUM_READ, root, Effects.ALLOW)])

        assert await check(db_session, user, child, Verbs.FORUM_READ)

    async def test_more_specific_deny_overrides_ancestor_allow(
        self, db_session, forums, user, implicit_roles
    ):
        root, parent, child = forums
        await implicit_roles(
            registered=[
                (Verbs.FORUM_READ, root, Effects.ALLOW),
                (Verbs.FORUM_READ, parent, Effects.DENY),
            ]
        )

        assert await check(db_session, user, root, Verbs.FORUM_READ)
        assert not await check(db_session, user, child, Verbs.FORUM_READ)

    async def test_more_specific_allow_overrides_ancestor_deny(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        root, _, child = forums
        await implicit_roles(registered=[(Verbs.FORUM_WRITE, root, Effects.DENY)])
        await make_role((Verbs.FORUM_WRITE, child, Effects.ALLOW), members=[user])

        assert await check(db_session, user, child, Verbs.FORUM_WRITE)

    async def test_another_roles_deny_on_the_same_forum_does_not_cancel_an_allow(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        root, _, _ = forums
        await implicit_roles(registered=[(Verbs.FORUM_WRITE, root, Effects.DENY)])
        await make_role((Verbs.FORUM_WRITE, root, Effects.ALLOW), members=[user])

        assert await check(db_session, user, root, Verbs.FORUM_WRITE)

    async def test_a_closer_deny_beats_another_roles_inherited_allow(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        root, _, child = forums
        await implicit_roles(registered=[(Verbs.FORUM_READ, child, Effects.DENY)])
        await make_role((Verbs.FORUM_READ, root, Effects.ALLOW), members=[user])

        assert await check(db_session, user, root, Verbs.FORUM_READ)
        assert not await check(db_session, user, child, Verbs.FORUM_READ)

    async def test_a_roles_child_deny_stands_until_another_role_allows_there(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        root, _, child = forums
        await implicit_roles()
        await make_role(
            (Verbs.FORUM_READ, root, Effects.ALLOW),
            (Verbs.FORUM_READ, child, Effects.DENY),
            members=[user],
        )
        assert not await check(db_session, user, child, Verbs.FORUM_READ)

        await make_role((Verbs.FORUM_READ, child, Effects.ALLOW), members=[user])
        assert await check(db_session, user, child, Verbs.FORUM_READ)

    async def test_grants_for_other_verbs_do_not_apply(
        self, db_session, forums, user, implicit_roles
    ):
        root, _, _ = forums
        await implicit_roles(registered=[(Verbs.FORUM_READ, root, Effects.ALLOW)])

        permissions = await ForumPermissions.load(db_session, user, [root])

        assert permissions.allowed(root) == {Verbs.FORUM_READ}


class TestModerate:
    async def test_moderate_implies_every_forum_verb(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        await implicit_roles()
        root, _, child = forums
        await make_role((Verbs.FORUM_MODERATE, root, Effects.ALLOW), members=[user])

        permissions = await ForumPermissions.load(db_session, user, [child])

        assert permissions.allowed(child) == FORUM_VERBS

    async def test_moderate_overrides_a_deny_on_another_verb(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        root, _, child = forums
        await implicit_roles(registered=[(Verbs.FORUM_WRITE, child, Effects.DENY)])
        await make_role((Verbs.FORUM_MODERATE, root, Effects.ALLOW), members=[user])

        assert await check(db_session, user, child, Verbs.FORUM_WRITE)

    async def test_moderate_cascades_despite_another_roles_deny_of_that_verb(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        root, _, child = forums
        await implicit_roles(registered=[(Verbs.FORUM_READ, root, Effects.DENY)])
        await make_role((Verbs.FORUM_MODERATE, root, Effects.ALLOW), members=[user])

        assert await check(db_session, user, child, Verbs.FORUM_READ)

    async def test_denied_moderate_no_longer_implies_other_verbs(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        root, _, child = forums
        await implicit_roles()
        await make_role(
            (Verbs.FORUM_MODERATE, root, Effects.ALLOW),
            (Verbs.FORUM_MODERATE, child, Effects.DENY),
            members=[user],
        )

        assert not await check(db_session, user, child, Verbs.FORUM_WRITE)


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
            subforum = await create(
                ForumFactory, parent_id=forum.id, heritage=[games_root.id, forum.id]
            )
            return forum, subforum

        return _make_game

    async def test_public_game_forums_are_readable_by_everyone(
        self, db_session, user, make_game, implicit_roles
    ):
        await implicit_roles()
        root, subforum = await make_game(public=True)

        assert await check(db_session, None, root, Verbs.FORUM_READ)
        assert await check(db_session, user, subforum, Verbs.FORUM_READ)
        assert not await check(db_session, user, root, Verbs.FORUM_WRITE)

    async def test_private_game_forums_are_not(
        self, db_session, user, make_game, implicit_roles
    ):
        await implicit_roles()
        root, _subforum = await make_game(public=False)

        assert not await check(db_session, user, root, Verbs.FORUM_READ)

    async def test_deny_on_a_subforum_overrides_public_read(
        self, db_session, user, make_game, implicit_roles
    ):
        root, subforum = await make_game(public=True)
        await implicit_roles(registered=[(Verbs.FORUM_READ, subforum, Effects.DENY)])

        assert await check(db_session, user, root, Verbs.FORUM_READ)
        assert not await check(db_session, user, subforum, Verbs.FORUM_READ)

    async def test_registered_deny_on_the_root_overrides_public_read_but_not_other_roles(
        self, db_session, user, make_game, make_role, implicit_roles
    ):
        root, subforum = await make_game(public=True)
        await implicit_roles(registered=[(Verbs.FORUM_READ, root, Effects.DENY)])
        assert not await check(db_session, user, root, Verbs.FORUM_READ)
        assert not await check(db_session, user, subforum, Verbs.FORUM_READ)

        await make_role((Verbs.FORUM_READ, root, Effects.ALLOW), members=[user])
        assert await check(db_session, user, subforum, Verbs.FORUM_READ)


class TestPlayerMode:
    @pytest.fixture
    async def tree(self, create, db_session):
        """site root -> games root -> game root -> game subforum, plus a site forum
        under the games root. The game's forums carry its ``game_id``."""
        site_root = await create(ForumFactory, heritage=[])
        games_root = await create(
            ForumFactory, parent_id=site_root.id, heritage=[site_root.id]
        )
        site_forum = await create(
            ForumFactory,
            parent_id=games_root.id,
            heritage=[site_root.id, games_root.id],
        )
        gm = await create(ActivatedUserFactory)
        game_root = await create(
            ForumFactory,
            parent_id=games_root.id,
            heritage=[site_root.id, games_root.id],
        )
        game = Game(
            title="Game",
            system=await create(SystemFactory),
            gm=gm,
            post_frequency="1/d",
            num_players=4,
            root_forum=game_root,
            gm_role=RoleFactory.build(owner=gm),
            player_role=RoleFactory.build(owner=gm),
            public=False,
        )
        db_session.add(game)
        await db_session.flush()
        game_root.game_id = game.id
        subforum = await create(
            ForumFactory,
            parent_id=game_root.id,
            heritage=[site_root.id, games_root.id, game_root.id],
            game_id=game.id,
        )
        return site_root, games_root, site_forum, game_root, subforum

    @pytest.mark.parametrize("scope", ["site_root", "games_root"])
    async def test_ancestor_moderator_gets_only_member_access_in_a_game(
        self, db_session, tree, user, make_role, implicit_roles, scope
    ):
        site_root, games_root, _site_forum, _game_root, subforum = tree
        await implicit_roles(registered=[(Verbs.FORUM_READ, site_root, Effects.ALLOW)])
        scoped = {"site_root": site_root, "games_root": games_root}[scope]
        await make_role((Verbs.FORUM_MODERATE, scoped, Effects.ALLOW), members=[user])
        user.moderator_mode = False

        permissions = await ForumPermissions.load(db_session, user, [subforum])

        assert permissions.allowed(subforum) == {Verbs.FORUM_READ}

    async def test_moderator_mode_keeps_ancestor_moderation_in_a_game(
        self, db_session, tree, user, make_role, implicit_roles
    ):
        _site_root, games_root, _site_forum, _game_root, subforum = tree
        await implicit_roles()
        await make_role(
            (Verbs.FORUM_MODERATE, games_root, Effects.ALLOW), members=[user]
        )
        user.moderator_mode = True

        permissions = await ForumPermissions.load(db_session, user, [subforum])

        assert permissions.allowed(subforum) == FORUM_VERBS

    async def test_gm_keeps_moderation_of_their_game(
        self, db_session, tree, user, make_role, implicit_roles
    ):
        _site_root, _games_root, _site_forum, game_root, subforum = tree
        await implicit_roles()
        await make_role(
            (Verbs.FORUM_MODERATE, game_root, Effects.ALLOW), members=[user]
        )
        user.moderator_mode = False

        assert await check(db_session, user, subforum, Verbs.FORUM_MODERATE)
        assert await check(db_session, user, subforum, Verbs.FORUM_WRITE)

    async def test_admin_is_not_bypassed_in_a_game_but_is_on_a_site_forum(
        self, db_session, tree, user, make_role, implicit_roles
    ):
        site_root, _games_root, site_forum, _game_root, subforum = tree
        await implicit_roles(registered=[(Verbs.FORUM_READ, site_root, Effects.ALLOW)])
        await make_role((Verbs.ADMIN, None, Effects.ALLOW), members=[user])
        user.moderator_mode = False

        permissions = await ForumPermissions.load(
            db_session, user, [subforum, site_forum]
        )

        assert permissions.allowed(subforum) == {Verbs.FORUM_READ}
        assert permissions.allowed(site_forum) == FORUM_VERBS

        user.moderator_mode = True
        permissions = await ForumPermissions.load(db_session, user, [subforum])
        assert permissions.allowed(subforum) == FORUM_VERBS

    async def test_site_forum_moderation_is_unaffected(
        self, db_session, tree, user, make_role, implicit_roles
    ):
        _site_root, games_root, site_forum, _game_root, _subforum = tree
        await implicit_roles()
        await make_role(
            (Verbs.FORUM_MODERATE, games_root, Effects.ALLOW), members=[user]
        )
        user.moderator_mode = False

        assert await check(db_session, user, site_forum, Verbs.FORUM_MODERATE)
        assert await moderated_roots(db_session, user) == [games_root]


class TestModeratedRoots:
    async def test_returns_the_forums_moderate_allows_name(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        root, parent, _child = forums
        await implicit_roles()
        await make_role(
            (Verbs.FORUM_MODERATE, parent, Effects.ALLOW),
            (Verbs.FORUM_WRITE, root, Effects.ALLOW),
            members=[user],
        )

        assert await moderated_roots(db_session, user) == [parent]

    async def test_another_roles_deny_does_not_drop_it(
        self, db_session, forums, user, make_role, implicit_roles
    ):
        _root, parent, _child = forums
        await implicit_roles(registered=[(Verbs.FORUM_MODERATE, parent, Effects.DENY)])
        await make_role((Verbs.FORUM_MODERATE, parent, Effects.ALLOW), members=[user])

        assert await moderated_roots(db_session, user) == [parent]


class TestLoad:
    async def test_resolves_several_forums_from_one_load(
        self, db_session, forums, user, implicit_roles
    ):
        root, parent, child = forums
        await implicit_roles(
            registered=[
                (Verbs.FORUM_READ, root, Effects.ALLOW),
                (Verbs.FORUM_READ, child, Effects.DENY),
            ]
        )

        permissions = await ForumPermissions.load(
            db_session, user, [root, parent, child]
        )

        assert permissions.has(root, Verbs.FORUM_READ)
        assert permissions.has(parent, Verbs.FORUM_READ)
        assert not permissions.has(child, Verbs.FORUM_READ)

    async def test_checking_an_unloaded_forum_raises(
        self, db_session, forums, user, implicit_roles
    ):
        await implicit_roles()
        root, _, child = forums

        permissions = await ForumPermissions.load(db_session, user, [root])

        with pytest.raises(ValueError):
            permissions.has(child, Verbs.FORUM_READ)
