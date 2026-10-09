import io

import pytest
from PIL import Image

from app.configs import configs
from app.models import RolePermission
from tests.factories import ForumFactory, PMFactory, RoleFactory, UserFactory
from tests.rbac.test_routes import (
    make_game_backed_by,
    make_game_role,
    make_role,
    make_site_moderator,
)


def _make_png_bytes(size=(10, 10)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color="red").save(buffer, format="PNG")
    return buffer.getvalue()


async def _give_permission(db_session, user, verb, **scope):
    """Attach a role holding one grant so the auth middleware sees it."""
    # Not owned by `user`: owning a role would itself grant roleAdmin/acp.
    role = RoleFactory.build()
    db_session.add(role)
    role.grant(verb, **scope)
    user.roles.append(role)
    await db_session.flush()


class TestGetCurrentUser:
    async def test_get_current_user_requires_auth(self, client):
        response = await client.get("/me")

        assert response.status_code == 403

    async def test_get_current_user_default_excludes_full_profile(self, authed_client):
        client, user = authed_client

        response = await client.get("/me")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == user.id
        assert body["username"] == user.username
        assert "joinDate" not in body
        assert "pronouns" not in body

    async def test_get_current_user_permissions_empty_without_grants(
        self, authed_client
    ):
        client, _user = authed_client

        response = await client.get("/me")

        assert response.status_code == 200
        body = response.json()
        assert body["permissions"] == []
        assert body["acp"] is False
        assert body["forumModerate"] is False
        assert body["siteModerate"] is False
        assert body["roleAdmin"] is False

    async def test_forum_moderator_gets_acp_access(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        forum = await create(ForumFactory)
        role = RoleFactory.build()
        db_session.add(role)
        role.grant(
            RolePermission.ValidPermissions.FORUM_MODERATE,
            scope_type=RolePermission.ScopeTypes.FORUM,
            scope_id=forum.id,
        )
        user.roles.append(role)
        await db_session.flush()

        response = await client.get("/me")

        body = response.json()
        assert body["acp"] is True
        assert body["forumModerate"] is True
        assert body["permissions"] == []

    async def test_owning_a_site_role_grants_role_admin_and_acp(
        self, authed_client, db_session
    ):
        client, user = authed_client
        await make_role(db_session, owner=user)

        body = (await client.get("/me")).json()

        assert body["roleAdmin"] is True
        assert body["acp"] is True
        assert body["forumModerate"] is False

    async def test_scoped_role_admin_holder_gets_role_admin_and_acp(
        self, authed_client, db_session
    ):
        client, user = authed_client
        target = await make_role(db_session)
        await _give_permission(
            db_session,
            user,
            RolePermission.ValidPermissions.ROLE_ADMIN,
            scope_type=RolePermission.ScopeTypes.ROLE,
            scope_id=target.id,
        )

        body = (await client.get("/me")).json()

        assert body["roleAdmin"] is True
        assert body["acp"] is True

    async def test_global_admin_gets_role_admin(self, authed_client, db_session):
        client, user = authed_client
        await _give_permission(db_session, user, RolePermission.ValidPermissions.ADMIN)

        body = (await client.get("/me")).json()

        assert body["roleAdmin"] is True
        assert body["siteModerate"] is True

    async def test_site_forum_moderator_is_a_site_moderator_with_role_admin(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        await make_site_moderator(db_session, create, user)

        body = (await client.get("/me")).json()

        assert body["siteModerate"] is True
        assert body["roleAdmin"] is True

    async def test_game_forum_moderator_is_not_a_site_moderator(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        game = await make_game_backed_by(db_session, create)
        await make_site_moderator(db_session, create, user, game=game)

        body = (await client.get("/me")).json()

        assert body["forumModerate"] is True
        assert body["siteModerate"] is False
        assert body["roleAdmin"] is False

    async def test_owning_only_a_game_role_does_not_grant_role_admin(
        self, authed_client, db_session, create
    ):
        client, user = authed_client
        game_role = await make_game_role(db_session, create)
        game_role.owner = user
        await db_session.flush()

        body = (await client.get("/me")).json()

        assert body["roleAdmin"] is False
        assert body["acp"] is False

    async def test_get_current_user_reports_global_permission_verbs(
        self, authed_client, db_session
    ):
        client, user = authed_client
        await _give_permission(
            db_session, user, RolePermission.ValidPermissions.MANAGE_USERS
        )

        response = await client.get("/me")

        assert response.status_code == 200
        body = response.json()
        assert body["permissions"] == ["manage_users"]
        assert body["acp"] is False

    async def test_get_current_user_full_includes_profile_fields(self, authed_client):
        client, _user = authed_client
        await client.post("/me", json={"pronouns": "they/them"})

        response = await client.get("/me?full=true")

        assert response.status_code == 200
        body = response.json()
        assert "joinDate" in body
        assert body["pronouns"] == "they/them"

    async def test_get_current_user_full_defaults_post_side_when_unset(
        self, authed_client
    ):
        client, _user = authed_client

        response = await client.get("/me?full=true")

        assert response.status_code == 200
        assert response.json()["postSide"] == "r"


class TestUpdateCurrentUser:
    async def test_update_current_user_requires_auth(self, client):
        response = await client.post("/me", json={"pronouns": "they/them"})

        assert response.status_code == 403

    async def test_update_current_user_sets_only_provided_fields(self, authed_client):
        client, _user = authed_client

        response = await client.post("/me", json={"pronouns": "they/them"})

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["updated"] == {"pronouns": "they/them"}

    async def test_update_current_user_rejects_future_birthday(self, authed_client):
        client, _user = authed_client

        response = await client.post("/me", json={"birthday": "2999-01-01"})

        assert response.status_code == 422


class TestUpdateCurrentUserAvatar:
    @pytest.fixture(autouse=True)
    def _avatars_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))
        return tmp_path

    async def test_update_avatar_requires_auth(self, client):
        response = await client.post(
            "/me/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )

        assert response.status_code == 403

    async def test_update_avatar_success(self, authed_client, _avatars_dir):
        client, user = authed_client

        response = await client.post(
            "/me/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["avatar"] == f"{configs.AVATARS_ROOT}/users/{user.id}.png"
        assert (_avatars_dir / "users" / f"{user.id}.png").exists()

    async def test_update_avatar_rejects_oversized_file(self, authed_client):
        client, _user = authed_client
        oversized = b"0" * (5 * 1024 * 1024 + 1)

        response = await client.post(
            "/me/avatar",
            files={"avatar": ("avatar.png", oversized, "image/png")},
        )

        assert response.status_code == 400

    async def test_update_avatar_rejects_invalid_image(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/me/avatar",
            files={"avatar": ("avatar.png", b"not an image", "image/png")},
        )

        assert response.status_code == 400


class TestDeleteCurrentUserAvatar:
    @pytest.fixture(autouse=True)
    def _avatars_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))
        return tmp_path

    async def test_delete_avatar_requires_auth(self, client):
        response = await client.delete("/me/avatar")

        assert response.status_code == 403

    async def test_delete_avatar_removes_existing_file(
        self, authed_client, _avatars_dir
    ):
        client, user = authed_client
        await client.post(
            "/me/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )

        response = await client.delete("/me/avatar")

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert not (_avatars_dir / "users" / f"{user.id}.png").exists()

    async def test_delete_avatar_without_existing_avatar(self, authed_client):
        client, _user = authed_client

        response = await client.delete("/me/avatar")

        assert response.status_code == 200
        assert response.json()["success"] is True


class TestUpdateCurrentUserPassword:
    async def test_update_password_requires_auth(self, client):
        response = await client.post(
            "/me/password",
            json={
                "oldPassword": "ValidPass1!",
                "password": "NewValidPass1!",
                "confirmPassword": "NewValidPass1!",
            },
        )

        assert response.status_code == 403

    async def test_update_password_success(self, authed_client):
        client, user = authed_client

        response = await client.post(
            "/me/password",
            json={
                "oldPassword": "ValidPass1!",
                "password": "NewValidPass1!",
                "confirmPassword": "NewValidPass1!",
            },
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert user.check_pass("NewValidPass1!")

    async def test_update_password_wrong_old_password(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/me/password",
            json={
                "oldPassword": "WrongPass1!",
                "password": "NewValidPass1!",
                "confirmPassword": "NewValidPass1!",
            },
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "invalid_old_password"

    async def test_update_password_mismatched_confirmation(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/me/password",
            json={
                "oldPassword": "ValidPass1!",
                "password": "NewValidPass1!",
                "confirmPassword": "Different1!",
            },
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "password_mismatch"


class TestGetHeader:
    async def test_get_header_requires_auth(self, client):
        response = await client.get("/me/header")

        assert response.status_code == 403

    async def test_get_header_counts_unread_pms(self, authed_client, create):
        client, user = authed_client
        other = await create(UserFactory, username="other")
        await create(PMFactory, recipient=user, sender=other, recipient_read=False)
        await create(PMFactory, recipient=user, sender=other, recipient_read=True)

        response = await client.get("/me/header")

        assert response.status_code == 200
        body = response.json()
        assert body["pmCount"] == 1
        assert body["characters"] == []
        assert body["games"] == []

    async def test_get_header_no_pms(self, authed_client):
        client, _user = authed_client

        response = await client.get("/me/header")

        assert response.status_code == 200
        assert response.json()["pmCount"] == 0
