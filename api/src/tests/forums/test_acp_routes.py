import pytest
from sqlalchemy import select, text

from app.models import Forum, Player, Role, RolePermission, UserRole
from app.repositories import GameRepository, PlayerRepository
from app.repositories.game_repository import GAMES_ROOT_FORUM_ID
from tests.factories import (
    ActivatedUserFactory,
    ForumFactory,
    RoleFactory,
    SystemFactory,
)

Verbs = RolePermission.ValidPermissions
ALLOW = RolePermission.Effects.ALLOW
DENY = RolePermission.Effects.DENY
FORUM_SCOPE = RolePermission.ScopeTypes.FORUM


@pytest.fixture(autouse=True)
def unseeded_admin_role(monkeypatch):
    """Like ``unseeded_system_roles``: keep a test's role from landing on the
    real Admin role's id."""
    monkeypatch.setattr(Role, "ADMIN_ID", -1)


@pytest.fixture
async def site(create, db_session, open_forums, wrap_in_savepoint):
    """Index (0) and Games (2), with Registered/Guest standing in for the
    system roles. Returns ``(index, registered, guest)``."""
    index = await create(ForumFactory, id=0, heritage=[], title="Index")
    await create(
        ForumFactory, id=GAMES_ROOT_FORUM_ID, parent_id=0, heritage=[0], title="Games"
    )
    await db_session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('forums', 'id'), "
            "(SELECT MAX(id) FROM forums))"
        )
    )
    registered, guest = await open_forums(index.id)
    return index, registered, guest


@pytest.fixture
async def board(create, site):
    """Index -> General -> Lounge -> Off Topic."""
    general = await create(
        ForumFactory, parent_id=0, heritage=[0], title="General", order=1
    )
    lounge = await create(
        ForumFactory,
        parent_id=general.id,
        heritage=[0, general.id],
        title="Lounge",
        order=1,
    )
    off_topic = await create(
        ForumFactory,
        parent_id=lounge.id,
        heritage=[0, general.id, lounge.id],
        title="Off Topic",
        order=1,
    )
    return {"general": general, "lounge": lounge, "off_topic": off_topic}


async def make_role(db_session, *, name=None, grants=(), game=None, members=()):
    """A role holding ``(verb, forum_id, effect)`` grants."""
    role = RoleFactory.build(**({"name": name} if name else {}))
    if game is not None:
        role.game_role = game.id
    db_session.add(role)
    for verb, forum_id, effect in grants:
        role.grant(verb, scope_type=FORUM_SCOPE, scope_id=forum_id, effect=effect)
    for member in members:
        role.users.append(member)
    await db_session.flush()
    return role


async def grants_on(db_session, forum, role):
    rows = await db_session.execute(
        select(RolePermission.permission, RolePermission.effect).where(
            RolePermission.role_id == role.id,
            RolePermission.scope_type == FORUM_SCOPE,
            RolePermission.scope_id == forum.id,
        )
    )
    return {permission.value: effect.value for permission, effect in rows}


@pytest.fixture
async def moderator(authed_client, db_session, board):
    """A client whose user moderates General (so not an admin)."""
    client, user = authed_client
    await make_role(
        db_session,
        grants=[(Verbs.FORUM_MODERATE, board["general"].id, ALLOW)],
        members=[user],
    )
    return client


@pytest.fixture
async def admin(authed_client, db_session, board):
    client, user = authed_client
    role = RoleFactory.build()
    db_session.add(role)
    role.grant(Verbs.ADMIN)
    role.users.append(user)
    await db_session.flush()
    return client


@pytest.fixture
async def gm(create):
    return await create(ActivatedUserFactory)


@pytest.fixture
async def make_game(create, db_session, gm, site):
    system = await create(SystemFactory)

    async def _make_game(title="Campaign", *, players=()):
        game = await GameRepository(db_session, principal=gm).create(
            title, system.id, [], gm.id, "1/d", 4, 1, None, None, True, None, None
        )
        player_repository = PlayerRepository(db_session, principal=gm)
        await player_repository.attach_player_to_game(
            game.id, gm.id, is_gm=True, state=Player.States.ACCEPTED
        )
        for user, state in players:
            await player_repository.attach_player_to_game(game.id, user.id, state=state)
        return game

    return _make_game


@pytest.fixture
async def game(make_game):
    return await make_game()


@pytest.fixture
async def gm_client(auth_as, gm):
    return auth_as(gm)


class TestGetForumPermissions:
    async def test_non_moderator_is_forbidden(self, authed_client, board):
        client, _user = authed_client

        response = await client.get(f"/forums/{board['general'].id}/permissions")

        assert response.status_code == 403

    async def test_lists_forum_verbs_with_read_first_and_moderate_last(
        self, moderator, board
    ):
        response = await moderator.get(f"/forums/{board['general'].id}/permissions")

        body = response.json()
        verbs = [verb["value"] for verb in body["verbs"]]
        assert len(verbs) == 10
        assert (verbs[0], verbs[-1]) == ("forum_read", "forum_moderate")
        assert body["can_grant_moderate"] is False

    async def test_non_game_forum_lists_registered_guest_and_granted_roles(
        self, moderator, db_session, board, site, game, monkeypatch
    ):
        _index, registered, guest = site
        general = board["general"]
        zeta = await make_role(
            db_session, name="Zeta", grants=[(Verbs.FORUM_READ, general.id, DENY)]
        )
        alpha = await make_role(
            db_session, name="Alpha", grants=[(Verbs.FORUM_WRITE, general.id, ALLOW)]
        )
        # Granted elsewhere only, so not listed here.
        await make_role(
            db_session,
            name="Elsewhere",
            grants=[(Verbs.FORUM_READ, board["lounge"].id, ALLOW)],
        )
        site_admin = await make_role(
            db_session, grants=[(Verbs.FORUM_READ, general.id, ALLOW)]
        )
        monkeypatch.setattr(Role, "ADMIN_ID", site_admin.id)
        # Granted here, but a game's roles belong to the game's forums.
        await make_role(
            db_session, game=game, grants=[(Verbs.FORUM_READ, general.id, ALLOW)]
        )

        response = await moderator.get(f"/forums/{general.id}/permissions")

        # The moderator fixture's own role is granted here too; ignore it.
        expected = {registered.id, guest.id, alpha.id, zeta.id}
        roles = [r for r in response.json()["roles"] if r["id"] in expected]
        assert len(roles) == 4
        assert [(r["id"], r["kind"]) for r in roles] == [
            (registered.id, "registered"),
            (guest.id, "guest"),
            (alpha.id, "site"),
            (zeta.id, "site"),
        ]
        assert roles[2]["grants"] == {"forum_write": "allow"}
        assert roles[3]["grants"] == {"forum_read": "deny"}
        listed_ids = {r["id"] for r in response.json()["roles"]}
        assert site_admin.id not in listed_ids

    async def test_inherited_follows_the_nearest_ancestor_grant(
        self, moderator, db_session, board
    ):
        general, lounge, off_topic = (
            board["general"],
            board["lounge"],
            board["off_topic"],
        )
        role = await make_role(
            db_session,
            grants=[
                (Verbs.FORUM_READ, general.id, ALLOW),
                (Verbs.FORUM_WRITE, general.id, ALLOW),
                (Verbs.FORUM_WRITE, lounge.id, DENY),
                # Listed on Off Topic because of this grant, which isn't inherited.
                (Verbs.FORUM_EDIT, off_topic.id, ALLOW),
            ],
        )

        response = await moderator.get(f"/forums/{off_topic.id}/permissions")

        listed = {r["id"]: r for r in response.json()["roles"]}[role.id]
        assert listed["grants"] == {"forum_edit": "allow"}
        assert listed["inherited"]["forum_read"] is True
        assert listed["inherited"]["forum_write"] is False
        assert listed["inherited"]["forum_edit"] is False

    async def test_inherited_moderate_implies_every_verb(
        self, moderator, db_session, board
    ):
        lounge = board["lounge"]
        role = await make_role(
            db_session,
            grants=[
                (Verbs.FORUM_MODERATE, board["general"].id, ALLOW),
                (Verbs.FORUM_READ, lounge.id, DENY),
            ],
        )

        response = await moderator.get(f"/forums/{lounge.id}/permissions")

        listed = {r["id"]: r for r in response.json()["roles"]}[role.id]
        assert all(listed["inherited"].values())
        assert listed["grants"] == {"forum_read": "deny"}

    async def test_forum_index_inherits_nothing(self, admin):
        response = await admin.get("/forums/0/permissions")

        body = response.json()
        assert body["can_grant_moderate"] is True
        assert not any(any(r["inherited"].values()) for r in body["roles"])

    async def test_game_forum_lists_the_games_roles_without_the_gm_role(
        self, gm_client, db_session, game
    ):
        zebra = await make_role(db_session, name="Zebra", game=game)
        scout = await make_role(db_session, name="Scout", game=game)

        response = await gm_client.get(f"/forums/{game.root_forum_id}/permissions")

        body = response.json()
        assert [(r["id"], r["kind"]) for r in body["roles"]] == [
            (game.player_role_id, "player"),
            (scout.id, "custom"),
            (zebra.id, "custom"),
        ]
        assert body["can_grant_moderate"] is False
        player = body["roles"][0]
        assert player["grants"]["forum_read"] == "allow"
        assert "forum_moderate" not in player["grants"]

    async def test_game_subforum_inherits_from_the_games_root(
        self, gm_client, create, game
    ):
        subforum = await create(
            ForumFactory,
            parent_id=game.root_forum_id,
            heritage=[0, GAMES_ROOT_FORUM_ID, game.root_forum_id],
            game_id=game.id,
        )

        response = await gm_client.get(f"/forums/{subforum.id}/permissions")

        player = response.json()["roles"][0]
        assert player["id"] == game.player_role_id
        assert player["grants"] == {}
        assert player["inherited"]["forum_read"] is True
        assert player["inherited"]["forum_moderate"] is False


class TestSetForumPermissions:
    async def put(self, client, forum, *entries):
        return await client.put(
            f"/forums/{forum.id}/permissions",
            json={"roles": [{"role_id": r.id, "grants": g} for r, g in entries]},
        )

    async def test_non_moderator_is_forbidden(self, authed_client, board):
        client, _user = authed_client

        response = await client.put(
            f"/forums/{board['general'].id}/permissions", json={"roles": []}
        )

        assert response.status_code == 403

    async def test_writes_only_the_differences_for_listed_roles(
        self, moderator, db_session, board
    ):
        lounge = board["lounge"]
        listed = await make_role(
            db_session,
            grants=[
                (Verbs.FORUM_READ, lounge.id, ALLOW),
                (Verbs.FORUM_WRITE, lounge.id, ALLOW),
                (Verbs.FORUM_DELETE, lounge.id, DENY),
            ],
        )
        unlisted = await make_role(
            db_session, grants=[(Verbs.FORUM_READ, lounge.id, ALLOW)]
        )

        response = await self.put(
            moderator,
            lounge,
            (
                listed,
                {"forum_read": "deny", "forum_delete": "deny", "forum_edit": "allow"},
            ),
        )

        assert response.status_code == 204
        # read flipped, write removed, delete untouched, edit added.
        assert await grants_on(db_session, lounge, listed) == {
            "forum_read": "deny",
            "forum_delete": "deny",
            "forum_edit": "allow",
        }
        assert await grants_on(db_session, lounge, unlisted) == {"forum_read": "allow"}

    async def test_grants_on_other_forums_are_left_alone(
        self, moderator, db_session, board
    ):
        general, lounge = board["general"], board["lounge"]
        role = await make_role(
            db_session, grants=[(Verbs.FORUM_READ, general.id, ALLOW)]
        )

        await self.put(moderator, lounge, (role, {}))

        assert await grants_on(db_session, general, role) == {"forum_read": "allow"}

    @pytest.mark.parametrize(
        ("existing", "requested"),
        [
            (None, "allow"),
            ("allow", "deny"),
            ("allow", None),
        ],
        ids=["added", "flipped", "removed"],
    )
    async def test_non_admin_cannot_change_moderate(
        self, moderator, db_session, board, existing, requested
    ):
        lounge = board["lounge"]
        role = await make_role(
            db_session,
            grants=[(Verbs.FORUM_READ, lounge.id, ALLOW)]
            + (
                [(Verbs.FORUM_MODERATE, lounge.id, RolePermission.Effects(existing))]
                if existing
                else []
            ),
        )
        before = await grants_on(db_session, lounge, role)
        grants = {"forum_write": "allow"}
        if requested:
            grants["forum_moderate"] = requested

        response = await self.put(moderator, lounge, (role, grants))

        assert response.status_code == 403
        assert await grants_on(db_session, lounge, role) == before

    async def test_non_admin_can_edit_other_verbs_beside_an_unchanged_moderate(
        self, moderator, db_session, board
    ):
        lounge = board["lounge"]
        role = await make_role(
            db_session, grants=[(Verbs.FORUM_MODERATE, lounge.id, ALLOW)]
        )

        response = await self.put(
            moderator, lounge, (role, {"forum_moderate": "allow", "forum_read": "deny"})
        )

        assert response.status_code == 204
        assert await grants_on(db_session, lounge, role) == {
            "forum_moderate": "allow",
            "forum_read": "deny",
        }

    async def test_admin_can_change_moderate(self, admin, db_session, board):
        lounge = board["lounge"]
        role = await make_role(db_session)

        response = await self.put(admin, lounge, (role, {"forum_moderate": "allow"}))

        assert response.status_code == 204
        assert await grants_on(db_session, lounge, role) == {"forum_moderate": "allow"}

    @pytest.mark.parametrize(
        ("grants", "released"),
        [
            ({"forum_read": "allow"}, True),
            ({"forum_moderate": "deny"}, True),
            ({"forum_moderate": "allow", "forum_read": "deny"}, False),
        ],
        ids=["removed", "denied", "unchanged"],
    )
    async def test_changing_moderate_releases_lapsed_moderators_roles(
        self, admin, db_session, board, fallback_owner, create, grants, released
    ):
        lounge = board["lounge"]
        owner = await create(ActivatedUserFactory)
        moderating = await make_role(
            db_session,
            grants=[(Verbs.FORUM_MODERATE, lounge.id, ALLOW)],
            members=[owner],
        )
        owned = await make_role(db_session)
        owned.owner = owner
        await db_session.flush()

        response = await self.put(admin, lounge, (moderating, grants))

        assert response.status_code == 204
        await db_session.refresh(owned)
        assert owned.owner_id == (fallback_owner.id if released else owner.id)

    async def test_clearing_moderate_on_one_save_releases_each_roles_members(
        self, admin, db_session, board, fallback_owner, create
    ):
        lounge = board["lounge"]
        user_a, user_b, user_c = [await create(ActivatedUserFactory) for _ in range(3)]
        role_a = await make_role(
            db_session,
            grants=[(Verbs.FORUM_MODERATE, lounge.id, ALLOW)],
            members=[user_a, user_c],
        )
        role_b = await make_role(
            db_session,
            grants=[(Verbs.FORUM_MODERATE, lounge.id, ALLOW)],
            members=[user_b],
        )
        # C also moderates another site forum, so losing role_a isn't enough.
        await make_role(
            db_session,
            grants=[(Verbs.FORUM_MODERATE, board["general"].id, ALLOW)],
            members=[user_c],
        )
        owned = {}
        for name, user in (("a", user_a), ("b", user_b), ("c", user_c)):
            owned[name] = await make_role(db_session)
            owned[name].owner = user
        await db_session.flush()

        response = await self.put(admin, lounge, (role_a, {}), (role_b, {}))

        assert response.status_code == 204
        for role in owned.values():
            await db_session.refresh(role)
        assert owned["a"].owner_id == fallback_owner.id
        assert owned["b"].owner_id == fallback_owner.id
        assert owned["c"].owner_id == user_c.id

    async def test_clearing_moderate_on_an_implicit_role_releases_nobody(
        self, admin, db_session, board, fallback_owner, create, site, monkeypatch
    ):
        _index, registered, guest = site
        lounge = board["lounge"]
        # The suite empties the implicit set; restore it for these two roles.
        monkeypatch.setattr(
            "app.repositories.rbac_repository.IMPLICIT_ROLE_IDS",
            frozenset({registered.id, guest.id}),
        )
        registered.grant(
            Verbs.FORUM_MODERATE, scope_type=FORUM_SCOPE, scope_id=lounge.id
        )
        # Registered membership is implicit, so real data has no such row. Planting
        # one is the only way for the skip to matter: without it, this member
        # would count as a moderator before the save and a lapsed one after.
        owner = await create(ActivatedUserFactory)
        db_session.add(UserRole(user_id=owner.id, role_id=registered.id))
        owned = await make_role(db_session)
        owned.owner = owner
        await db_session.flush()

        response = await self.put(admin, lounge, (registered, {}))

        assert response.status_code == 204
        assert await grants_on(db_session, lounge, registered) == {}
        await db_session.refresh(owned)
        assert owned.owner_id == owner.id

    async def test_non_forum_verb_is_rejected(self, moderator, db_session, board):
        role = await make_role(db_session)

        response = await self.put(
            moderator, board["lounge"], (role, {"access_acp": "allow"})
        )

        assert response.status_code == 400

    async def test_duplicate_role_is_rejected_and_nothing_is_written(
        self, moderator, db_session, board
    ):
        lounge = board["lounge"]
        role = await make_role(db_session)

        response = await self.put(
            moderator,
            lounge,
            (role, {"forum_read": "allow"}),
            (role, {"forum_read": "deny"}),
        )

        assert response.status_code == 400
        assert await grants_on(db_session, lounge, role) == {}

    async def test_ineligible_roles_are_rejected_and_nothing_is_written(
        self, moderator, db_session, board, game, monkeypatch
    ):
        lounge = board["lounge"]
        fine = await make_role(db_session)
        site_admin = await make_role(db_session)
        monkeypatch.setattr(Role, "ADMIN_ID", site_admin.id)
        entry = {"forum_read": "allow"}

        for bad in (site_admin, await db_session.get(Role, game.player_role_id)):
            response = await self.put(moderator, lounge, (fine, entry), (bad, entry))

            assert response.status_code == 400
        assert await grants_on(db_session, lounge, fine) == {}

    async def test_game_forum_takes_only_the_games_roles(
        self, gm_client, db_session, make_game, game
    ):
        other_game = await make_game("Other")
        root = await db_session.get(Forum, game.root_forum_id)
        scout = await make_role(db_session, name="Scout", game=game)
        foreign = await make_role(db_session, name="Foreign", game=other_game)
        site_role = await make_role(db_session)
        gm_role = await db_session.get(Role, game.gm_role_id)
        entry = {"forum_read": "allow"}

        accepted = await self.put(gm_client, root, (scout, entry))
        rejected = [
            (await self.put(gm_client, root, (bad, entry))).status_code
            for bad in (foreign, site_role, gm_role)
        ]

        assert accepted.status_code == 204
        assert await grants_on(db_session, root, scout) == entry
        assert rejected == [400, 400, 400]


class TestSearchPermissionRoles:
    async def test_lists_only_addable_site_roles_ordered_by_name(
        self, moderator, db_session, board, game, monkeypatch
    ):
        site_admin = await make_role(db_session, name="Admin Role")
        monkeypatch.setattr(Role, "ADMIN_ID", site_admin.id)
        game_role = await make_role(db_session, name="Game Thing", game=game)
        beta = await make_role(db_session, name="Beta")
        alpha = await make_role(db_session, name="Alpha")

        response = await moderator.get(
            f"/forums/{board['general'].id}/permissions/roles"
        )

        assert response.status_code == 200
        # Admin, Registered, Guest (all real roles here) and the game's role
        # are left out.
        returned = [r["id"] for r in response.json()["roles"]]
        # The moderator fixture's own site role is addable too; ignore it.
        assert [i for i in returned if i in {alpha.id, beta.id}] == [alpha.id, beta.id]
        assert site_admin.id not in returned
        assert game_role.id not in returned

    async def test_filter_is_a_case_insensitive_substring_match(
        self, moderator, db_session, board
    ):
        match = await make_role(db_session, name="Scoutmaster")
        await make_role(db_session, name="Other")

        response = await moderator.get(
            f"/forums/{board['general'].id}/permissions/roles", params={"filter": "OUT"}
        )

        assert [r["id"] for r in response.json()["roles"]] == [match.id]

    async def test_results_are_capped_at_twenty(self, moderator, db_session, board):
        for index in range(21):
            await make_role(db_session, name=f"Bulk {index:02}")

        response = await moderator.get(
            f"/forums/{board['general'].id}/permissions/roles",
            params={"filter": "Bulk"},
        )

        assert len(response.json()["roles"]) == 20

    async def test_game_forum_is_rejected(self, gm_client, game):
        response = await gm_client.get(
            f"/forums/{game.root_forum_id}/permissions/roles"
        )

        assert response.status_code == 400

    async def test_non_moderator_is_forbidden(self, authed_client, board):
        client, _user = authed_client

        response = await client.get(f"/forums/{board['general'].id}/permissions/roles")

        assert response.status_code == 403


class TestGetGameRoles:
    async def test_lists_player_then_custom_roles_with_members_and_players(
        self, gm_client, db_session, create, make_game, gm
    ):
        zed, amy, applicant = (
            await create(ActivatedUserFactory, username="zed"),
            await create(ActivatedUserFactory, username="amy"),
            await create(ActivatedUserFactory, username="applicant"),
        )
        game = await make_game(
            players=[
                (zed, Player.States.ACCEPTED),
                (amy, Player.States.ACCEPTED),
                (applicant, Player.States.APPLIED),
            ]
        )
        zebra = await make_role(db_session, name="Zebra", game=game, members=[zed, amy])
        scout = await make_role(db_session, name="Scout", game=game)

        response = await gm_client.get(f"/forums/{game.root_forum_id}/roles")

        body = response.json()
        assert [(r["id"], r["kind"]) for r in body["roles"]] == [
            (game.player_role_id, "player"),
            (scout.id, "custom"),
            (zebra.id, "custom"),
        ]
        assert [m["username"] for m in body["roles"][2]["members"]] == ["amy", "zed"]
        usernames = [p["username"] for p in body["players"]]
        assert set(usernames) == {gm.username, "zed", "amy"}
        assert usernames.index("amy") < usernames.index("zed")

    async def test_non_moderator_is_forbidden(self, authed_client, game):
        client, _user = authed_client

        response = await client.get(f"/forums/{game.root_forum_id}/roles")

        assert response.status_code == 403

    async def test_game_subforum_is_rejected(self, gm_client, create, game):
        subforum = await create(
            ForumFactory,
            parent_id=game.root_forum_id,
            heritage=[0, GAMES_ROOT_FORUM_ID, game.root_forum_id],
            game_id=game.id,
        )

        responses = [
            await gm_client.get(f"/forums/{subforum.id}/roles"),
            await gm_client.post(
                f"/forums/{subforum.id}/roles", json={"name": "Scout"}
            ),
        ]

        assert [r.status_code for r in responses] == [400, 400]


class TestSiteForumRoles:
    async def test_site_forum_is_rejected(self, admin, board):
        response = await admin.get(f"/forums/{board['general'].id}/roles")

        assert response.status_code == 400


class TestCreateGameRole:
    async def test_creates_a_role_owned_by_the_gm_for_the_game(
        self, gm_client, db_session, game, gm
    ):
        response = await gm_client.post(
            f"/forums/{game.root_forum_id}/roles", json={"name": "  Scout "}
        )

        assert response.status_code == 200
        role = await db_session.get(Role, response.json()["id"])
        assert (role.name, role.game_role, role.owner_id) == ("Scout", game.id, gm.id)

    async def test_duplicate_name_in_the_same_game_conflicts(self, gm_client, game):
        url = f"/forums/{game.root_forum_id}/roles"
        await gm_client.post(url, json={"name": "Scout"})

        response = await gm_client.post(url, json={"name": "Scout"})

        assert response.status_code == 409

    async def test_two_games_can_share_a_role_name(self, gm_client, make_game, game):
        other_game = await make_game("Other")

        first = await gm_client.post(
            f"/forums/{game.root_forum_id}/roles", json={"name": "Scout"}
        )
        second = await gm_client.post(
            f"/forums/{other_game.root_forum_id}/roles", json={"name": "Scout"}
        )

        assert (first.status_code, second.status_code) == (200, 200)


class TestUpdateGameRole:
    async def test_renames_a_custom_role(self, gm_client, db_session, game):
        role = await make_role(db_session, name="Scout", game=game)

        response = await gm_client.patch(
            f"/forums/{game.root_forum_id}/roles/{role.id}", json={"name": "Ranger"}
        )

        assert response.status_code == 204
        await db_session.refresh(role)
        assert (role.name, role.plural) == ("Ranger", "Rangers")

    async def test_duplicate_name_conflicts(self, gm_client, db_session, game):
        await make_role(db_session, name="Scout", game=game)
        role = await make_role(db_session, name="Ranger", game=game)

        response = await gm_client.patch(
            f"/forums/{game.root_forum_id}/roles/{role.id}", json={"name": "Scout"}
        )

        assert response.status_code == 409

    async def test_player_role_is_forbidden_and_gm_and_other_games_roles_not_found(
        self, gm_client, db_session, make_game, game
    ):
        other_game = await make_game("Other")
        foreign = await make_role(db_session, name="Foreign", game=other_game)
        url = f"/forums/{game.root_forum_id}/roles"

        player_response = await gm_client.patch(
            f"{url}/{game.player_role_id}", json={"name": "Heroes"}
        )
        gm_response = await gm_client.patch(
            f"{url}/{game.gm_role_id}", json={"name": "Boss"}
        )
        foreign_response = await gm_client.patch(
            f"{url}/{foreign.id}", json={"name": "Boss"}
        )

        assert (
            player_response.status_code,
            gm_response.status_code,
            foreign_response.status_code,
        ) == (403, 404, 404)


class TestDeleteGameRole:
    async def test_soft_deletes_a_custom_role(self, gm_client, db_session, game):
        role = await make_role(db_session, name="Scout", game=game)

        response = await gm_client.delete(
            f"/forums/{game.root_forum_id}/roles/{role.id}"
        )

        assert response.status_code == 204
        deleted = await db_session.scalar(
            select(Role.deleted)
            .where(Role.id == role.id)
            .execution_options(skip_filter=True)
        )
        assert deleted is not None

    async def test_player_role_is_forbidden_and_gm_and_other_games_roles_not_found(
        self, gm_client, db_session, make_game, game
    ):
        foreign = await make_role(db_session, game=await make_game("Other"))
        url = f"/forums/{game.root_forum_id}/roles"

        player_response = await gm_client.delete(f"{url}/{game.player_role_id}")
        gm_response = await gm_client.delete(f"{url}/{game.gm_role_id}")
        foreign_response = await gm_client.delete(f"{url}/{foreign.id}")

        assert (
            player_response.status_code,
            gm_response.status_code,
            foreign_response.status_code,
        ) == (403, 404, 404)


class TestSetGameRoleMembers:
    async def test_replaces_the_membership(
        self, gm_client, db_session, create, make_game
    ):
        keep, drop, add = [await create(ActivatedUserFactory) for _ in range(3)]
        game = await make_game(
            players=[(u, Player.States.ACCEPTED) for u in (keep, drop, add)]
        )
        role = await make_role(db_session, game=game, members=[keep, drop])

        response = await gm_client.put(
            f"/forums/{game.root_forum_id}/roles/{role.id}/members",
            json={"user_ids": [keep.id, add.id]},
        )

        assert response.status_code == 204
        await db_session.refresh(role, ["users"])
        assert {u.id for u in role.users} == {keep.id, add.id}

    async def test_rejects_users_who_are_not_accepted_players(
        self, gm_client, db_session, create, make_game
    ):
        applicant, outsider = [await create(ActivatedUserFactory) for _ in range(2)]
        game = await make_game(players=[(applicant, Player.States.APPLIED)])
        role = await make_role(db_session, game=game)

        responses = [
            await gm_client.put(
                f"/forums/{game.root_forum_id}/roles/{role.id}/members",
                json={"user_ids": [user.id]},
            )
            for user in (applicant, outsider)
        ]

        assert [r.status_code for r in responses] == [400, 400]
        await db_session.refresh(role, ["users"])
        assert role.users == []

    async def test_player_role_is_forbidden_and_gm_role_is_not_found(
        self, gm_client, game, gm
    ):
        url = f"/forums/{game.root_forum_id}/roles"

        player_response = await gm_client.put(
            f"{url}/{game.player_role_id}/members", json={"user_ids": [gm.id]}
        )
        gm_response = await gm_client.put(
            f"{url}/{game.gm_role_id}/members", json={"user_ids": [gm.id]}
        )

        assert (player_response.status_code, gm_response.status_code) == (403, 404)
