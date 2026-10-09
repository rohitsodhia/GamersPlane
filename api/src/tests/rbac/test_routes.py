import pytest
from sqlalchemy import select

from app.models import Game, RolePermission
from tests.factories import ForumFactory, RoleFactory, SystemFactory, UserFactory

Verbs = RolePermission.ValidPermissions
Scopes = RolePermission.ScopeTypes
Effects = RolePermission.Effects


async def give_permission(db_session, user, verb, *, scope_type=None, scope_id=None):
    """Attach a role holding one grant to `user` so the auth middleware sees it.

    The role gets its own owner: owners can now see and manage their roles, so
    owning the helper role would leak extra access into the test.
    """
    role = RoleFactory.build()
    db_session.add(role)
    role.grant(verb, scope_type=scope_type, scope_id=scope_id)
    user.roles.append(role)
    await db_session.flush()
    return role


async def make_admin(db_session, user):
    return await give_permission(db_session, user, Verbs.ADMIN)


async def make_role(db_session, *, name=None, owner=None, members=(), grants=()):
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if owner is not None:
        kwargs["owner"] = owner
    role = RoleFactory.build(**kwargs)
    db_session.add(role)
    for member in members:
        role.users.append(member)
    for verb, scope_type, scope_id in grants:
        role.grant(verb, scope_type=scope_type, scope_id=scope_id)
    await db_session.flush()
    return role


@pytest.fixture
def protect_role(monkeypatch):
    """Point the repository's hard-lock at a role built by the test.

    The production lock targets role id 1 / member id 1; rather than force those
    ids past a shared, non-resetting Postgres sequence, we repoint the module
    constants at whatever role/user the test made.
    """

    def _protect(role, *, member_id=None):
        monkeypatch.setattr(
            "app.repositories.rbac_repository.PROTECTED_ROLE_ID", role.id
        )
        if member_id is not None:
            monkeypatch.setattr(
                "app.repositories.rbac_repository.PROTECTED_ROLE_MEMBER_ID",
                member_id,
            )

    return _protect


@pytest.fixture
def implicit_role(monkeypatch):
    """Treat a role built by the test as an implicit-membership role.

    Same reasoning as ``protect_role``: repoint the repository's id set rather
    than force ids 2/3 past the shared sequence.
    """

    def _implicit(role):
        monkeypatch.setattr(
            "app.repositories.rbac_repository.IMPLICIT_ROLE_IDS",
            frozenset({role.id}),
        )

    return _implicit


async def make_game_backed_by(db_session, create, *, gm_role=None, player_role=None):
    """A game whose GM/player roles are the given ones (fresh roles otherwise)."""
    system = await create(SystemFactory)
    gm = await create(UserFactory)
    root_forum = await create(ForumFactory)
    game = Game(
        title="Backed Game",
        system=system,
        gm=gm,
        post_frequency="1/d",
        num_players=4,
        root_forum=root_forum,
        gm_role=gm_role or await make_role(db_session),
        player_role=player_role or await make_role(db_session),
        public=True,
    )
    db_session.add(game)
    await db_session.flush()
    return game


async def make_game_role(db_session, create, *, name=None):
    """A role scoped to a game (``Role.game_role`` points at that game).

    Also builds the backing game graph (system/GM/forum/game) plus plain GM and
    player roles to satisfy the game's NOT NULL role columns; those roles have
    ``game_role IS NULL``, so callers asserting on exact result sets should
    account for them.
    """
    game = await make_game_backed_by(db_session, create)
    role = await make_role(db_session, name=name)
    role.game = game
    await db_session.flush()
    return role


class TestGetPermissions:
    async def test_requires_auth(self, client):
        response = await client.get("/rbac/permissions")

        assert response.status_code == 403

    async def test_lists_every_api_grantable_verb_with_label(self, authed_client):
        client, _user = authed_client

        response = await client.get("/rbac/permissions")

        assert response.status_code == 200
        permissions = response.json()["permissions"]
        # Exact set: the seed-only `admin` verb (api_grantable=False) must be
        # filtered out, every other verb must be present.
        assert {p["value"] for p in permissions} == {
            "access_acp",
            "manage_users",
            "role_admin",
            "forum_read",
            "forum_write",
            "forum_edit",
            "forum_delete",
            "forum_create_thread",
            "forum_delete_thread",
            "forum_add_poll",
            "forum_add_rolls",
            "forum_add_draws",
            "forum_moderate",
        }
        acp = next(p for p in permissions if p["value"] == "access_acp")
        assert acp["label"] == "Access ACP"

    async def test_reports_allowed_scope_types_per_verb(self, authed_client):
        client, _user = authed_client

        response = await client.get("/rbac/permissions")

        by_value = {p["value"]: p["scopes"] for p in response.json()["permissions"]}
        assert by_value["access_acp"] == ["global"]
        assert by_value["forum_read"] == ["forum"]
        assert by_value["role_admin"] == ["role"]


class TestGetRoles:
    async def test_requires_auth(self, client):
        response = await client.get("/rbac/roles")

        assert response.status_code == 403

    async def test_admin_sees_every_role(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        roles = [await make_role(db_session) for _ in range(3)]

        response = await client.get("/rbac/roles")

        assert response.status_code == 200
        returned = {r["id"] for r in response.json()["roles"]}
        assert {r.id for r in roles} <= returned

    async def test_non_admin_sees_only_role_admin_scoped_roles(
        self, authed_client, db_session
    ):
        client, user = authed_client
        managed = await make_role(db_session)
        await make_role(db_session)  # unmanaged
        await give_permission(
            db_session,
            user,
            Verbs.ROLE_ADMIN,
            scope_type=Scopes.ROLE,
            scope_id=managed.id,
        )

        response = await client.get("/rbac/roles")

        assert response.status_code == 200
        assert {r["id"] for r in response.json()["roles"]} == {managed.id}

    async def test_user_without_grants_sees_nothing(self, authed_client, db_session):
        client, _user = authed_client
        await make_role(db_session)

        response = await client.get("/rbac/roles")

        assert response.status_code == 200
        assert response.json()["roles"] == []

    async def test_scoped_deny_hides_an_otherwise_managed_role(
        self, authed_client, db_session
    ):
        client, user = authed_client
        role = await make_role(db_session)
        await give_permission(
            db_session,
            user,
            Verbs.ROLE_ADMIN,
            scope_type=Scopes.ROLE,
            scope_id=role.id,
        )
        denier = await give_permission(
            db_session,
            user,
            Verbs.ROLE_ADMIN,
            scope_type=Scopes.ROLE,
            scope_id=role.id,
        )
        denier.grants[0].effect = Effects.DENY
        await db_session.flush()

        response = await client.get("/rbac/roles")

        assert {r["id"] for r in response.json()["roles"]} == set()

    async def test_filter_matches_name_substring(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        alpha = await make_role(db_session, name="Alpha Squad")
        await make_role(db_session, name="Beta Squad")

        response = await client.get("/rbac/roles", params={"filter": "alpha"})

        assert {r["id"] for r in response.json()["roles"]} == {alpha.id}

    async def test_defaults_to_non_game_roles(self, authed_client, db_session, create):
        client, user = authed_client
        await make_admin(db_session, user)
        plain = await make_role(db_session)
        game_role = await make_game_role(db_session, create)

        response = await client.get("/rbac/roles")

        assert response.status_code == 200
        returned = {r["id"] for r in response.json()["roles"]}
        assert plain.id in returned
        assert game_role.id not in returned

    async def test_game_roles_true_returns_only_game_roles(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        plain = await make_role(db_session)
        game_role = await make_game_role(db_session, create)

        response = await client.get("/rbac/roles", params={"game_roles": "true"})

        assert response.status_code == 200
        returned = {r["id"] for r in response.json()["roles"]}
        assert game_role.id in returned
        assert plain.id not in returned

    async def test_role_row_reports_owner_and_counts(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        member_one = (await make_role(db_session)).owner
        member_two = (await make_role(db_session)).owner
        role = await make_role(
            db_session,
            members=[member_one, member_two],
            grants=[(Verbs.ACP_ACCESS, None, None)],
        )

        response = await client.get("/rbac/roles", params={"filter": role.name})

        row = next(r for r in response.json()["roles"] if r["id"] == role.id)
        assert row["name"] == role.name
        assert row["owner"] == {"id": role.owner.id, "username": role.owner.username}
        assert row["user_count"] == 2
        assert row["grant_count"] == 1


async def make_site_moderator(db_session, create, user, *, game=None):
    """Make `user` moderate a forum: a site forum, or `game`'s forum if given."""
    forum = await create(ForumFactory, game_id=game.id if game else None)
    await give_permission(
        db_session,
        user,
        Verbs.FORUM_MODERATE,
        scope_type=Scopes.FORUM,
        scope_id=forum.id,
    )
    return forum


class TestCreateRole:
    async def test_plain_user_is_forbidden(self, authed_client):
        client, _user = authed_client

        response = await client.post("/rbac/roles", json={"name": "Editors"})

        assert response.status_code == 403

    async def test_game_forum_moderator_is_forbidden(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        game = await make_game_backed_by(db_session, create)
        await make_site_moderator(db_session, create, user, game=game)

        response = await client.post("/rbac/roles", json={"name": "Editors"})

        assert response.status_code == 403

    async def test_site_moderator_creates_role_they_own_with_no_grants(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        await make_site_moderator(db_session, create, user)

        response = await client.post("/rbac/roles", json={"name": "Editors"})

        assert response.status_code == 200
        detail = (await client.get(f"/rbac/roles/{response.json()['id']}")).json()
        assert detail["owner"]["id"] == user.id
        assert detail["grants"] == []

    async def test_site_moderator_may_name_themselves_owner(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        await make_site_moderator(db_session, create, user)

        response = await client.post(
            "/rbac/roles", json={"name": "Editors", "owner_id": user.id}
        )

        assert response.status_code == 200

    async def test_site_moderator_cannot_set_another_owner(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        await make_site_moderator(db_session, create, user)
        other = (await make_role(db_session)).owner

        response = await client.post(
            "/rbac/roles", json={"name": "Editors", "owner_id": other.id}
        )

        assert response.status_code == 403

    async def test_creates_role_owned_by_caller_by_default(
        self, authed_client, db_session
    ):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.post("/rbac/roles", json={"name": "Editors"})

        assert response.status_code == 200
        new_id = response.json()["id"]
        detail = await client.get(f"/rbac/roles/{new_id}")
        assert detail.json()["name"] == "Editors"
        assert detail.json()["owner"]["id"] == user.id

    async def test_creates_role_with_explicit_owner(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        other = await make_role(db_session)  # gives us a persisted user
        owner = other.owner

        response = await client.post(
            "/rbac/roles", json={"name": "Editors", "owner_id": owner.id}
        )

        new_id = response.json()["id"]
        detail = await client.get(f"/rbac/roles/{new_id}")
        assert detail.json()["owner"]["id"] == owner.id

    async def test_unknown_owner_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.post(
            "/rbac/roles", json={"name": "Editors", "owner_id": 999999}
        )

        assert response.status_code == 404

    async def test_duplicate_name_returns_409(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        await make_role(db_session, name="Editors")

        response = await client.post("/rbac/roles", json={"name": "Editors"})

        assert response.status_code == 409
        # The client's db_session override skips DBSessionDependency's rollback,
        # so the swallowed IntegrityError would poison later tests otherwise.
        await db_session.rollback()

    async def test_name_of_soft_deleted_role_can_be_reused(
        self, authed_client, db_session
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        stale = await make_role(db_session, name="Editors")
        await client.delete(f"/rbac/roles/{stale.id}")

        response = await client.post("/rbac/roles", json={"name": "Editors"})

        assert response.status_code == 200
        assert response.json()["id"] != stale.id

    @pytest.mark.parametrize("name", ["   ", "x" * 49])
    async def test_invalid_name_returns_422(self, authed_client, db_session, name):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.post("/rbac/roles", json={"name": name})

        assert response.status_code == 422

    async def test_name_is_stripped(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.post("/rbac/roles", json={"name": "  Spaced  "})

        detail = await client.get(f"/rbac/roles/{response.json()['id']}")
        assert detail.json()["name"] == "Spaced"


class TestGetRole:
    async def test_requires_auth(self, client):
        response = await client.get("/rbac/roles/1")

        assert response.status_code == 403

    async def test_unknown_role_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.get("/rbac/roles/999999")

        assert response.status_code == 404

    async def test_non_manager_gets_404(self, authed_client, db_session):
        client, _user = authed_client
        role = await make_role(db_session)

        response = await client.get(f"/rbac/roles/{role.id}")

        assert response.status_code == 404

    async def test_role_admin_scoped_user_can_view_that_role(
        self, authed_client, db_session
    ):
        client, user = authed_client
        role = await make_role(db_session)
        await give_permission(
            db_session,
            user,
            Verbs.ROLE_ADMIN,
            scope_type=Scopes.ROLE,
            scope_id=role.id,
        )

        response = await client.get(f"/rbac/roles/{role.id}")

        assert response.status_code == 200
        assert response.json()["id"] == role.id

    async def test_detail_includes_owner_users_and_grants(
        self, authed_client, db_session
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        member = (await make_role(db_session)).owner
        role = await make_role(
            db_session,
            members=[member],
            grants=[(Verbs.ACP_ACCESS, None, None)],
        )

        body = (await client.get(f"/rbac/roles/{role.id}")).json()

        assert body["owner"]["id"] == role.owner.id
        assert [u["id"] for u in body["users"]] == [member.id]
        grant = body["grants"][0]
        assert grant["permission"] == {"value": "access_acp", "label": "Access ACP"}
        assert grant["effect"] == "allow"
        assert grant["scope_type"] is None
        assert grant["scope_id"] is None

    async def test_global_grant_description_is_the_label(
        self, authed_client, db_session
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session, grants=[(Verbs.ACP_ACCESS, None, None)])

        body = (await client.get(f"/rbac/roles/{role.id}")).json()

        assert body["grants"][0]["description"] == "Access ACP"

    async def test_forum_scoped_grant_description_resolves_forum_title(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        forum = await create(ForumFactory, title="General")
        role = await make_role(
            db_session,
            grants=[(Verbs.FORUM_MODERATE, Scopes.FORUM, forum.id)],
        )

        body = (await client.get(f"/rbac/roles/{role.id}")).json()

        assert body["grants"][0]["description"] == (
            f"Moderate Forum - General (#{forum.id})"
        )

    async def test_role_scoped_grant_description_resolves_role_name(
        self, authed_client, db_session
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        target = await make_role(db_session, name="Section Mods")
        role = await make_role(
            db_session,
            grants=[(Verbs.ROLE_ADMIN, Scopes.ROLE, target.id)],
        )

        body = (await client.get(f"/rbac/roles/{role.id}")).json()

        assert body["grants"][0]["description"] == (
            f"Manage Role - Section Mods (#{target.id})"
        )

    async def test_moderated_forum_ids_lists_only_forums_the_viewer_moderates(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        moderated = await create(ForumFactory)
        other = await create(ForumFactory)
        await give_permission(
            db_session,
            user,
            Verbs.FORUM_MODERATE,
            scope_type=Scopes.FORUM,
            scope_id=moderated.id,
        )
        role = await make_role(
            db_session,
            owner=user,
            grants=[
                (Verbs.FORUM_READ, Scopes.FORUM, moderated.id),
                (Verbs.FORUM_READ, Scopes.FORUM, other.id),
            ],
        )

        body = (await client.get(f"/rbac/roles/{role.id}")).json()

        assert body["moderated_forum_ids"] == [moderated.id]

    async def test_moderated_forum_ids_ignores_non_forum_grants(
        self, authed_client, db_session
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        target = await make_role(db_session)
        role = await make_role(
            db_session,
            grants=[
                (Verbs.ACP_ACCESS, None, None),
                (Verbs.ROLE_ADMIN, Scopes.ROLE, target.id),
            ],
        )

        body = (await client.get(f"/rbac/roles/{role.id}")).json()

        assert body["moderated_forum_ids"] == []


class TestUpdateRole:
    async def test_unrelated_user_gets_404(self, authed_client, db_session):
        client, _user = authed_client
        role = await make_role(db_session)

        response = await client.patch(f"/rbac/roles/{role.id}", json={"name": "New"})

        assert response.status_code == 404

    async def test_renames_role(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session, name="Old")

        response = await client.patch(f"/rbac/roles/{role.id}", json={"name": "New"})

        assert response.status_code == 204
        assert (await client.get(f"/rbac/roles/{role.id}")).json()["name"] == "New"

    async def test_reassigns_owner(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        new_owner = (await make_role(db_session)).owner

        response = await client.patch(
            f"/rbac/roles/{role.id}", json={"owner_id": new_owner.id}
        )

        assert response.status_code == 204
        detail = await client.get(f"/rbac/roles/{role.id}")
        assert detail.json()["owner"]["id"] == new_owner.id

    async def test_omitted_fields_are_left_untouched(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session, name="Keep")

        response = await client.patch(f"/rbac/roles/{role.id}", json={})

        assert response.status_code == 204
        assert (await client.get(f"/rbac/roles/{role.id}")).json()["name"] == "Keep"

    async def test_unknown_role_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.patch("/rbac/roles/999999", json={"name": "New"})

        assert response.status_code == 404

    async def test_unknown_owner_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        response = await client.patch(
            f"/rbac/roles/{role.id}", json={"owner_id": 999999}
        )

        assert response.status_code == 404

    async def test_duplicate_name_returns_409(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        await make_role(db_session, name="Taken")
        role = await make_role(db_session, name="Free")

        response = await client.patch(f"/rbac/roles/{role.id}", json={"name": "Taken"})

        assert response.status_code == 409
        await db_session.rollback()

    async def test_protected_role_cannot_be_edited(
        self, authed_client, db_session, protect_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session, name="Site Owner")
        protect_role(role)

        response = await client.patch(
            f"/rbac/roles/{role.id}", json={"name": "Renamed"}
        )

        assert response.status_code == 403
        assert (await client.get(f"/rbac/roles/{role.id}")).json()[
            "name"
        ] == "Site Owner"


class TestDeleteRole:
    async def test_unrelated_user_gets_404(self, authed_client, db_session):
        client, _user = authed_client
        role = await make_role(db_session)

        response = await client.delete(f"/rbac/roles/{role.id}")

        assert response.status_code == 404

    async def test_soft_deletes_role(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        response = await client.delete(f"/rbac/roles/{role.id}")

        assert response.status_code == 204
        assert (await client.get(f"/rbac/roles/{role.id}")).status_code == 404

    async def test_unknown_role_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.delete("/rbac/roles/999999")

        assert response.status_code == 404

    @pytest.mark.parametrize("game_role", ["gm_role", "player_role"])
    async def test_role_backing_a_game_returns_409(
        self, authed_client, db_session, create, game_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        await make_game_backed_by(db_session, create, **{game_role: role})

        response = await client.delete(f"/rbac/roles/{role.id}")

        assert response.status_code == 409
        assert (await client.get(f"/rbac/roles/{role.id}")).status_code == 200

    async def test_protected_role_cannot_be_deleted(
        self, authed_client, db_session, protect_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        protect_role(role)

        response = await client.delete(f"/rbac/roles/{role.id}")

        assert response.status_code == 403
        assert (await client.get(f"/rbac/roles/{role.id}")).status_code == 200

    async def test_implicit_role_cannot_be_deleted(
        self, authed_client, db_session, implicit_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        implicit_role(role)

        response = await client.delete(f"/rbac/roles/{role.id}")

        assert response.status_code == 403
        assert (await client.get(f"/rbac/roles/{role.id}")).status_code == 200


class TestCreateGrant:
    async def test_requires_admin(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/rbac/roles/1/grants", json={"permission": "access_acp"}
        )

        assert response.status_code == 403

    async def test_unknown_role_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.post(
            "/rbac/roles/999999/grants", json={"permission": "access_acp"}
        )

        assert response.status_code == 404

    async def test_adds_a_global_grant(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        response = await client.post(
            f"/rbac/roles/{role.id}/grants", json={"permission": "access_acp"}
        )

        assert response.status_code == 204
        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert body["grants"][0]["permission"]["value"] == "access_acp"
        assert body["grants"][0]["effect"] == "allow"

    async def test_adds_a_forum_scoped_grant(self, authed_client, db_session, create):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        forum = await create(ForumFactory)

        response = await client.post(
            f"/rbac/roles/{role.id}/grants",
            json={
                "permission": "forum_moderate",
                "scope_type": "forum",
                "scope_id": forum.id,
            },
        )

        assert response.status_code == 204
        grant = (await client.get(f"/rbac/roles/{role.id}")).json()["grants"][0]
        assert grant["scope_type"] == "forum"
        assert grant["scope_id"] == forum.id

    async def test_deny_effect_is_stored(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        await client.post(
            f"/rbac/roles/{role.id}/grants",
            json={"permission": "access_acp", "effect": "deny"},
        )

        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert body["grants"][0]["effect"] == "deny"

    async def test_scope_illegal_for_verb_returns_400(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        response = await client.post(
            f"/rbac/roles/{role.id}/grants",
            json={"permission": "access_acp", "scope_type": "forum", "scope_id": 1},
        )

        assert response.status_code == 400

    async def test_admin_verb_cannot_be_granted_via_api(
        self, authed_client, db_session
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        response = await client.post(
            f"/rbac/roles/{role.id}/grants", json={"permission": "admin"}
        )

        assert response.status_code == 400
        assert (await client.get(f"/rbac/roles/{role.id}")).json()["grants"] == []

    @pytest.mark.parametrize("permission", ["role_admin", "forum_read"])
    async def test_scope_requiring_verb_without_scope_returns_400(
        self, authed_client, db_session, permission
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        response = await client.post(
            f"/rbac/roles/{role.id}/grants", json={"permission": permission}
        )

        assert response.status_code == 400

    @pytest.mark.parametrize(
        "extra",
        [
            {"permission": "forum_read", "scope_type": "forum"},
            {"permission": "access_acp", "scope_id": 5},
        ],
    )
    async def test_lopsided_scope_returns_422(self, authed_client, db_session, extra):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        response = await client.post(f"/rbac/roles/{role.id}/grants", json=extra)

        assert response.status_code == 422

    async def test_unknown_forum_scope_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        response = await client.post(
            f"/rbac/roles/{role.id}/grants",
            json={
                "permission": "forum_moderate",
                "scope_type": "forum",
                "scope_id": 999999,
            },
        )

        assert response.status_code == 404

    async def test_unknown_role_scope_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        response = await client.post(
            f"/rbac/roles/{role.id}/grants",
            json={
                "permission": "role_admin",
                "scope_type": "role",
                "scope_id": 999999,
            },
        )

        assert response.status_code == 404

    async def test_duplicate_grant_returns_409(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        payload = {"permission": "access_acp"}
        await client.post(f"/rbac/roles/{role.id}/grants", json=payload)

        response = await client.post(f"/rbac/roles/{role.id}/grants", json=payload)

        assert response.status_code == 409
        await db_session.rollback()

    async def test_protected_role_grants_cannot_be_added(
        self, authed_client, db_session, protect_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        protect_role(role)

        response = await client.post(
            f"/rbac/roles/{role.id}/grants", json={"permission": "access_acp"}
        )

        assert response.status_code == 403
        assert (await client.get(f"/rbac/roles/{role.id}")).json()["grants"] == []

    async def test_implicit_role_grants_can_be_added(
        self, authed_client, db_session, implicit_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        implicit_role(role)

        response = await client.post(
            f"/rbac/roles/{role.id}/grants", json={"permission": "access_acp"}
        )

        assert response.status_code == 204
        grants = (await client.get(f"/rbac/roles/{role.id}")).json()["grants"]
        assert [g["permission"]["value"] for g in grants] == ["access_acp"]


class TestUpdateGrant:
    async def test_requires_admin(self, authed_client):
        client, _user = authed_client

        response = await client.patch("/rbac/roles/1/grants/1", json={"effect": "deny"})

        assert response.status_code == 403

    async def test_toggles_effect(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session, grants=[(Verbs.ACP_ACCESS, None, None)])
        grant_id = role.grants[0].id

        response = await client.patch(
            f"/rbac/roles/{role.id}/grants/{grant_id}", json={"effect": "deny"}
        )

        assert response.status_code == 204
        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert body["grants"][0]["effect"] == "deny"

    async def test_unknown_role_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.patch(
            "/rbac/roles/999999/grants/1", json={"effect": "deny"}
        )

        assert response.status_code == 404

    async def test_grant_belonging_to_another_role_returns_404(
        self, authed_client, db_session
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        other = await make_role(db_session, grants=[(Verbs.ACP_ACCESS, None, None)])
        role = await make_role(db_session)

        response = await client.patch(
            f"/rbac/roles/{role.id}/grants/{other.grants[0].id}",
            json={"effect": "deny"},
        )

        assert response.status_code == 404

    async def test_protected_role_grant_cannot_be_edited(
        self, authed_client, db_session, protect_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session, grants=[(Verbs.ACP_ACCESS, None, None)])
        protect_role(role)
        grant_id = role.grants[0].id

        response = await client.patch(
            f"/rbac/roles/{role.id}/grants/{grant_id}", json={"effect": "deny"}
        )

        assert response.status_code == 403
        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert body["grants"][0]["effect"] == "allow"


class TestDeleteGrant:
    async def test_requires_admin(self, authed_client):
        client, _user = authed_client

        response = await client.delete("/rbac/roles/1/grants/1")

        assert response.status_code == 403

    async def test_hard_deletes_the_grant(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session, grants=[(Verbs.ACP_ACCESS, None, None)])
        grant_id = role.grants[0].id

        response = await client.delete(f"/rbac/roles/{role.id}/grants/{grant_id}")

        assert response.status_code == 204
        assert (await client.get(f"/rbac/roles/{role.id}")).json()["grants"] == []
        rows = (
            (
                await db_session.execute(
                    select(RolePermission).where(RolePermission.id == grant_id)
                )
            )
            .scalars()
            .all()
        )
        assert rows == []

    async def test_unknown_role_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.delete("/rbac/roles/999999/grants/1")

        assert response.status_code == 404

    async def test_protected_role_grant_cannot_be_deleted(
        self, authed_client, db_session, protect_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session, grants=[(Verbs.ACP_ACCESS, None, None)])
        protect_role(role)
        grant_id = role.grants[0].id

        response = await client.delete(f"/rbac/roles/{role.id}/grants/{grant_id}")

        assert response.status_code == 403
        assert len((await client.get(f"/rbac/roles/{role.id}")).json()["grants"]) == 1


class TestAddUserToRole:
    async def test_unrelated_user_gets_404(self, authed_client, db_session):
        client, user = authed_client
        role = await make_role(db_session)

        response = await client.post(
            f"/rbac/roles/{role.id}/users", json={"user_id": user.id}
        )

        assert response.status_code == 404

    async def test_unknown_role_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.post(
            "/rbac/roles/999999/users", json={"user_id": user.id}
        )

        assert response.status_code == 404

    async def test_unknown_user_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        response = await client.post(
            f"/rbac/roles/{role.id}/users", json={"user_id": 999999}
        )

        assert response.status_code == 404

    async def test_adds_the_user(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        target = (await make_role(db_session)).owner

        response = await client.post(
            f"/rbac/roles/{role.id}/users", json={"user_id": target.id}
        )

        assert response.status_code == 204
        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert [u["id"] for u in body["users"]] == [target.id]

    async def test_re_adding_a_member_is_a_noop(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        target = (await make_role(db_session)).owner
        role = await make_role(db_session, members=[target])

        response = await client.post(
            f"/rbac/roles/{role.id}/users", json={"user_id": target.id}
        )

        assert response.status_code == 204
        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert [u["id"] for u in body["users"]] == [target.id]

    async def test_users_can_still_be_added_to_the_protected_role(
        self, authed_client, db_session, protect_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        protect_role(role)
        target = (await make_role(db_session)).owner

        response = await client.post(
            f"/rbac/roles/{role.id}/users", json={"user_id": target.id}
        )

        assert response.status_code == 204
        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert target.id in [u["id"] for u in body["users"]]

    async def test_users_cannot_be_added_to_an_implicit_role(
        self, authed_client, db_session, implicit_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        implicit_role(role)
        target = (await make_role(db_session)).owner

        response = await client.post(
            f"/rbac/roles/{role.id}/users", json={"user_id": target.id}
        )

        assert response.status_code == 403
        assert (await client.get(f"/rbac/roles/{role.id}")).json()["users"] == []


class TestRemoveUserFromRole:
    async def test_unrelated_user_gets_404(self, authed_client, db_session):
        client, user = authed_client
        role = await make_role(db_session)

        response = await client.delete(f"/rbac/roles/{role.id}/users/{user.id}")

        assert response.status_code == 404

    async def test_unknown_role_returns_404(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)

        response = await client.delete("/rbac/roles/999999/users/1")

        assert response.status_code == 404

    async def test_removes_the_user(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        target = (await make_role(db_session)).owner
        role = await make_role(db_session, members=[target])

        response = await client.delete(f"/rbac/roles/{role.id}/users/{target.id}")

        assert response.status_code == 204
        assert (await client.get(f"/rbac/roles/{role.id}")).json()["users"] == []

    async def test_removing_a_non_member_is_a_noop(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        stranger = (await make_role(db_session)).owner

        response = await client.delete(f"/rbac/roles/{role.id}/users/{stranger.id}")

        assert response.status_code == 204

    async def test_protected_member_cannot_be_removed_from_protected_role(
        self, authed_client, db_session, protect_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        protected_member = (await make_role(db_session)).owner
        role = await make_role(db_session, members=[protected_member])
        protect_role(role, member_id=protected_member.id)

        response = await client.delete(
            f"/rbac/roles/{role.id}/users/{protected_member.id}"
        )

        assert response.status_code == 403
        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert [u["id"] for u in body["users"]] == [protected_member.id]

    async def test_other_members_can_be_removed_from_the_protected_role(
        self, authed_client, db_session, protect_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        protected_member = (await make_role(db_session)).owner
        other_member = (await make_role(db_session)).owner
        role = await make_role(db_session, members=[protected_member, other_member])
        protect_role(role, member_id=protected_member.id)

        response = await client.delete(f"/rbac/roles/{role.id}/users/{other_member.id}")

        assert response.status_code == 204
        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert [u["id"] for u in body["users"]] == [protected_member.id]

    async def test_users_cannot_be_removed_from_an_implicit_role(
        self, authed_client, db_session, implicit_role
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        member = (await make_role(db_session)).owner
        role = await make_role(db_session, members=[member])
        implicit_role(role)

        response = await client.delete(f"/rbac/roles/{role.id}/users/{member.id}")

        assert response.status_code == 403
        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert [u["id"] for u in body["users"]] == [member.id]


class TestGameBackedRoles:
    """A game's GM role is fixed and both its GM and Player roles take members
    from the game's player list."""

    @pytest.fixture
    async def gm_role(self, authed_client, db_session, create):
        _client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(
            db_session, grants=[(Verbs.FORUM_MODERATE, Scopes.FORUM, 99)]
        )
        await make_game_backed_by(db_session, create, gm_role=role)
        return role

    @pytest.fixture
    async def player_role(self, authed_client, db_session, create):
        _client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        await make_game_backed_by(db_session, create, player_role=role)
        return role

    async def test_gm_role_cannot_be_renamed(self, authed_client, gm_role):
        client, _user = authed_client

        response = await client.patch(f"/rbac/roles/{gm_role.id}", json={"name": "New"})

        assert response.status_code == 403

    async def test_gm_role_grants_cannot_be_changed(self, authed_client, gm_role):
        client, _user = authed_client
        grant_id = gm_role.grants[0].id

        created = await client.post(
            f"/rbac/roles/{gm_role.id}/grants", json={"permission": "access_acp"}
        )
        updated = await client.patch(
            f"/rbac/roles/{gm_role.id}/grants/{grant_id}", json={"effect": "deny"}
        )
        deleted = await client.delete(f"/rbac/roles/{gm_role.id}/grants/{grant_id}")

        assert (created.status_code, updated.status_code, deleted.status_code) == (
            403,
            403,
            403,
        )
        grants = (await client.get(f"/rbac/roles/{gm_role.id}")).json()["grants"]
        assert [(g["id"], g["effect"]) for g in grants] == [(grant_id, "allow")]

    async def assert_members_locked(self, client, db_session, role):
        member = (await make_role(db_session)).owner
        other = (await make_role(db_session)).owner
        await db_session.refresh(role, ["users"])
        role.users.append(member)
        await db_session.flush()

        added = await client.post(
            f"/rbac/roles/{role.id}/users", json={"user_id": other.id}
        )
        removed = await client.delete(f"/rbac/roles/{role.id}/users/{member.id}")

        assert (added.status_code, removed.status_code) == (403, 403)
        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert [u["id"] for u in body["users"]] == [member.id]

    async def test_gm_role_members_are_managed_by_the_game(
        self, authed_client, db_session, gm_role
    ):
        client, _user = authed_client

        await self.assert_members_locked(client, db_session, gm_role)

    async def test_player_role_members_are_managed_by_the_game(
        self, authed_client, db_session, player_role
    ):
        client, _user = authed_client

        await self.assert_members_locked(client, db_session, player_role)

    async def test_player_role_can_still_be_renamed_and_granted(
        self, authed_client, player_role
    ):
        client, _user = authed_client

        renamed = await client.patch(
            f"/rbac/roles/{player_role.id}", json={"name": "Adventurers"}
        )
        granted = await client.post(
            f"/rbac/roles/{player_role.id}/grants", json={"permission": "access_acp"}
        )

        assert (renamed.status_code, granted.status_code) == (204, 204)


async def make_managed_role(db_session, user, who, **kwargs):
    """A site role `user` manages as its owner or as a scoped role_admin holder."""
    if who == "owner":
        return await make_role(db_session, owner=user, **kwargs)
    role = await make_role(db_session, **kwargs)
    await give_permission(
        db_session, user, Verbs.ROLE_ADMIN, scope_type=Scopes.ROLE, scope_id=role.id
    )
    return role


class TestSiteRoleDelegation:
    """Non-admins can manage site roles they own or hold a scoped role_admin on."""

    @pytest.mark.parametrize("who", ["owner", "role_admin"])
    async def test_can_rename(self, authed_client, db_session, who):
        client, user = authed_client
        role = await make_managed_role(db_session, user, who, name="Old")

        response = await client.patch(f"/rbac/roles/{role.id}", json={"name": "New"})

        assert response.status_code == 204
        assert (await client.get(f"/rbac/roles/{role.id}")).json()["name"] == "New"

    @pytest.mark.parametrize("who", ["owner", "role_admin"])
    async def test_can_add_and_remove_members(self, authed_client, db_session, who):
        client, user = authed_client
        role = await make_managed_role(db_session, user, who)
        member = (await make_role(db_session)).owner

        added = await client.post(
            f"/rbac/roles/{role.id}/users", json={"user_id": member.id}
        )
        users_after_add = (await client.get(f"/rbac/roles/{role.id}")).json()["users"]
        removed = await client.delete(f"/rbac/roles/{role.id}/users/{member.id}")
        users_after_remove = (await client.get(f"/rbac/roles/{role.id}")).json()[
            "users"
        ]

        assert (added.status_code, removed.status_code) == (204, 204)
        assert [u["id"] for u in users_after_add] == [member.id]
        assert users_after_remove == []

    async def test_owner_can_delete(self, authed_client, db_session):
        client, user = authed_client
        role = await make_managed_role(db_session, user, "owner")

        response = await client.delete(f"/rbac/roles/{role.id}")

        assert response.status_code == 204
        assert (await client.get(f"/rbac/roles/{role.id}")).status_code == 404

    async def test_role_admin_holder_cannot_delete(self, authed_client, db_session):
        client, user = authed_client
        role = await make_managed_role(db_session, user, "role_admin")

        response = await client.delete(f"/rbac/roles/{role.id}")

        assert response.status_code == 403
        assert (await client.get(f"/rbac/roles/{role.id}")).status_code == 200

    async def test_scoped_deny_beats_allow(self, authed_client, db_session):
        client, user = authed_client
        role = await make_managed_role(db_session, user, "role_admin")
        denier = await give_permission(
            db_session, user, Verbs.ROLE_ADMIN, scope_type=Scopes.ROLE, scope_id=role.id
        )
        denier.grants[0].effect = Effects.DENY
        await db_session.flush()

        response = await client.patch(f"/rbac/roles/{role.id}", json={"name": "New"})

        assert response.status_code == 404

    @pytest.mark.parametrize("who", ["owner", "role_admin"])
    async def test_cannot_touch_grants_or_create_roles(
        self, authed_client, db_session, who
    ):
        client, user = authed_client
        role = await make_managed_role(
            db_session, user, who, grants=[(Verbs.ACP_ACCESS, None, None)]
        )
        grant_id = role.grants[0].id

        created = await client.post(
            f"/rbac/roles/{role.id}/grants", json={"permission": "manage_users"}
        )
        updated = await client.patch(
            f"/rbac/roles/{role.id}/grants/{grant_id}", json={"effect": "deny"}
        )
        deleted = await client.delete(f"/rbac/roles/{role.id}/grants/{grant_id}")
        new_role = await client.post("/rbac/roles", json={"name": "Mine"})

        assert [r.status_code for r in (created, updated, deleted, new_role)] == [
            403
        ] * 4
        grants = (await client.get(f"/rbac/roles/{role.id}")).json()["grants"]
        assert [(g["id"], g["effect"]) for g in grants] == [(grant_id, "allow")]

    @pytest.mark.parametrize("who", ["owner", "role_admin"])
    async def test_cannot_change_owner(self, authed_client, db_session, who):
        client, user = authed_client
        role = await make_managed_role(db_session, user, who)
        other = (await make_role(db_session)).owner

        response = await client.patch(
            f"/rbac/roles/{role.id}", json={"name": "New", "owner_id": other.id}
        )

        assert response.status_code == 403
        body = (await client.get(f"/rbac/roles/{role.id}")).json()
        assert body["owner"]["id"] == role.owner_id
        assert body["name"] == role.name

    async def test_resending_the_current_owner_is_allowed(
        self, authed_client, db_session
    ):
        client, user = authed_client
        role = await make_managed_role(db_session, user, "owner")

        response = await client.patch(
            f"/rbac/roles/{role.id}", json={"name": "New", "owner_id": user.id}
        )

        assert response.status_code == 204

    @pytest.mark.parametrize("who", ["owner", "role_admin"])
    @pytest.mark.parametrize("lock", ["protected", "implicit"])
    async def test_locked_roles_stay_admin_only(
        self, authed_client, db_session, request, who, lock
    ):
        client, user = authed_client
        role = await make_managed_role(db_session, user, who)
        if lock == "protected":
            request.getfixturevalue("protect_role")(role)
        else:
            request.getfixturevalue("implicit_role")(role)

        renamed = await client.patch(f"/rbac/roles/{role.id}", json={"name": "New"})
        added = await client.post(
            f"/rbac/roles/{role.id}/users", json={"user_id": user.id}
        )
        deleted = await client.delete(f"/rbac/roles/{role.id}")

        assert [r.status_code for r in (renamed, added, deleted)] == [403] * 3

    async def test_game_role_owner_cannot_use_rbac(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        role = await make_game_role(db_session, create)
        role.owner = user
        await db_session.flush()

        listed = await client.get("/rbac/roles", params={"game_roles": "true"})
        fetched = await client.get(f"/rbac/roles/{role.id}")
        renamed = await client.patch(f"/rbac/roles/{role.id}", json={"name": "New"})

        assert listed.json()["roles"] == []
        assert (fetched.status_code, renamed.status_code) == (404, 404)

    async def test_game_role_admin_holder_can_view_but_not_mutate(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        role = await make_game_role(db_session, create)
        await give_permission(
            db_session, user, Verbs.ROLE_ADMIN, scope_type=Scopes.ROLE, scope_id=role.id
        )

        fetched = await client.get(f"/rbac/roles/{role.id}")
        renamed = await client.patch(f"/rbac/roles/{role.id}", json={"name": "New"})
        deleted = await client.delete(f"/rbac/roles/{role.id}")

        assert fetched.status_code == 200
        assert fetched.json()["role_admin"] is False
        assert (renamed.status_code, deleted.status_code) == (403, 403)

    async def test_list_includes_owned_site_roles_only(self, authed_client, db_session):
        client, user = authed_client
        owned = await make_role(db_session, owner=user)
        await make_role(db_session)  # someone else's

        response = await client.get("/rbac/roles")

        assert {r["id"] for r in response.json()["roles"]} == {owned.id}


class TestGetRoleCapabilities:
    async def test_admin_can_do_everything(self, authed_client, db_session):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)

        body = (await client.get(f"/rbac/roles/{role.id}")).json()

        assert [body[k] for k in ("role_admin", "can_delete", "admin")] == [True] * 3

    async def test_owner_cannot_manage_grants_or_owner(self, authed_client, db_session):
        client, user = authed_client
        role = await make_managed_role(db_session, user, "owner")

        body = (await client.get(f"/rbac/roles/{role.id}")).json()

        assert (body["role_admin"], body["can_delete"], body["admin"]) == (
            True,
            True,
            False,
        )

    async def test_role_admin_holder_cannot_delete(self, authed_client, db_session):
        client, user = authed_client
        role = await make_managed_role(db_session, user, "role_admin")

        body = (await client.get(f"/rbac/roles/{role.id}")).json()

        assert (body["role_admin"], body["can_delete"], body["admin"]) == (
            True,
            False,
            False,
        )

    async def test_managers_lists_roles_with_an_allowing_role_admin_grant(
        self, authed_client, db_session
    ):
        client, user = authed_client
        await make_admin(db_session, user)
        role = await make_role(db_session)
        manager = await make_role(
            db_session, grants=[(Verbs.ROLE_ADMIN, Scopes.ROLE, role.id)]
        )
        denied = await make_role(
            db_session, grants=[(Verbs.ROLE_ADMIN, Scopes.ROLE, role.id)]
        )
        denied.grants[0].effect = Effects.DENY
        await make_role(db_session, grants=[(Verbs.ROLE_ADMIN, Scopes.ROLE, 999999)])
        await db_session.flush()

        body = (await client.get(f"/rbac/roles/{role.id}")).json()

        assert body["managers"] == [{"id": manager.id, "name": manager.name}]


async def make_moderating_owner(db_session, create, *, forum=None):
    """A user who moderates a site forum through a role, and owns another role.

    Returns ``(owner, moderating_role, owned_role)``.
    """
    forum = forum or await create(ForumFactory)
    owner = (await make_role(db_session)).owner
    moderating = await make_role(
        db_session,
        members=[owner],
        grants=[(Verbs.FORUM_MODERATE, Scopes.FORUM, forum.id)],
    )
    owned = await make_role(db_session, owner=owner)
    return owner, moderating, owned


class TestReleaseOrphanedRoles:
    """A user who stops being a site moderator hands their site roles to the
    fallback owner."""

    @pytest.fixture
    async def admin_client(self, authed_client, db_session, fallback_owner):
        client, user = authed_client
        await make_admin(db_session, user)
        return client

    async def owner_of(self, client, role):
        return (await client.get(f"/rbac/roles/{role.id}")).json()["owner"]["id"]

    async def test_removing_the_member_releases_their_roles(
        self, admin_client, db_session, create, fallback_owner
    ):
        owner, moderating, owned = await make_moderating_owner(db_session, create)

        response = await admin_client.delete(
            f"/rbac/roles/{moderating.id}/users/{owner.id}"
        )

        assert response.status_code == 204
        assert await self.owner_of(admin_client, owned) == fallback_owner.id

    async def test_deleting_the_grant_releases_member_roles(
        self, admin_client, db_session, create, fallback_owner
    ):
        _owner, moderating, owned = await make_moderating_owner(db_session, create)

        response = await admin_client.delete(
            f"/rbac/roles/{moderating.id}/grants/{moderating.grants[0].id}"
        )

        assert response.status_code == 204
        assert await self.owner_of(admin_client, owned) == fallback_owner.id

    async def test_denying_the_grant_releases_member_roles(
        self, admin_client, db_session, create, fallback_owner
    ):
        _owner, moderating, owned = await make_moderating_owner(db_session, create)

        response = await admin_client.patch(
            f"/rbac/roles/{moderating.id}/grants/{moderating.grants[0].id}",
            json={"effect": "deny"},
        )

        assert response.status_code == 204
        assert await self.owner_of(admin_client, owned) == fallback_owner.id

    async def test_deleting_the_role_releases_member_roles(
        self, admin_client, db_session, create, fallback_owner
    ):
        _owner, moderating, owned = await make_moderating_owner(db_session, create)

        response = await admin_client.delete(f"/rbac/roles/{moderating.id}")

        assert response.status_code == 204
        assert await self.owner_of(admin_client, owned) == fallback_owner.id

    async def test_losing_admin_through_a_role_releases_member_roles(
        self, admin_client, db_session, fallback_owner
    ):
        # Admin is the only thing making this member a site moderator, so
        # leaving the role has to count as losing moderation.
        owner = (await make_role(db_session)).owner
        admin_role = await make_role(
            db_session, members=[owner], grants=[(Verbs.ADMIN, None, None)]
        )
        owned = await make_role(db_session, owner=owner)

        response = await admin_client.delete(
            f"/rbac/roles/{admin_role.id}/users/{owner.id}"
        )

        assert response.status_code == 204
        assert await self.owner_of(admin_client, owned) == fallback_owner.id

    async def test_still_moderating_through_another_role_keeps_ownership(
        self, admin_client, db_session, create, fallback_owner
    ):
        owner, moderating, owned = await make_moderating_owner(db_session, create)
        forum = await create(ForumFactory)
        await make_role(
            db_session,
            members=[owner],
            grants=[(Verbs.FORUM_MODERATE, Scopes.FORUM, forum.id)],
        )

        await admin_client.delete(f"/rbac/roles/{moderating.id}/users/{owner.id}")

        assert await self.owner_of(admin_client, owned) == owner.id

    async def test_owner_who_never_moderated_keeps_their_roles(
        self, admin_client, db_session, fallback_owner
    ):
        plain = await make_role(db_session)
        owner = plain.owner
        member_of = await make_role(db_session, members=[owner])
        owned = await make_role(db_session, owner=owner)

        await admin_client.delete(f"/rbac/roles/{member_of.id}/users/{owner.id}")

        assert await self.owner_of(admin_client, owned) == owner.id

    async def test_game_forum_moderator_keeps_their_roles(
        self, admin_client, db_session, create, fallback_owner
    ):
        game = await make_game_backed_by(db_session, create)
        game_forum = await create(ForumFactory, game_id=game.id)
        owner, moderating, owned = await make_moderating_owner(
            db_session, create, forum=game_forum
        )

        await admin_client.delete(f"/rbac/roles/{moderating.id}/users/{owner.id}")

        assert await self.owner_of(admin_client, owned) == owner.id

    async def test_admin_owner_keeps_their_roles(
        self, admin_client, db_session, create, fallback_owner
    ):
        owner, moderating, owned = await make_moderating_owner(db_session, create)
        await make_admin(db_session, owner)

        await admin_client.delete(f"/rbac/roles/{moderating.id}/users/{owner.id}")

        assert await self.owner_of(admin_client, owned) == owner.id

    @pytest.mark.parametrize("kind", ["game", "protected", "implicit"])
    async def test_game_and_locked_roles_are_never_reassigned(
        self, admin_client, db_session, create, fallback_owner, request, kind
    ):
        owner, moderating, owned = await make_moderating_owner(db_session, create)
        if kind == "game":
            locked = await make_game_role(db_session, create)
            locked.owner = owner
            await db_session.flush()
        else:
            locked = owned
            owned = await make_role(db_session, owner=owner)
            fixture = "protect_role" if kind == "protected" else "implicit_role"
            request.getfixturevalue(fixture)(locked)

        await admin_client.delete(f"/rbac/roles/{moderating.id}/users/{owner.id}")

        assert await self.owner_of(admin_client, owned) == fallback_owner.id
        await db_session.refresh(locked)
        assert locked.owner_id == owner.id
