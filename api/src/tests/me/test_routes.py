import io

import pytest
from PIL import Image

from app.configs import configs
from tests.factories import PMFactory, UserFactory


def _make_png_bytes(size=(10, 10)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color="red").save(buffer, format="PNG")
    return buffer.getvalue()


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
        assert body["avatar"] == f"{configs.AVATARS_ROOT}/{user.id}.png"
        assert (_avatars_dir / f"{user.id}.png").exists()

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

    async def test_delete_avatar_removes_existing_file(self, authed_client, _avatars_dir):
        client, user = authed_client
        await client.post(
            "/me/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )

        response = await client.delete("/me/avatar")

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert not (_avatars_dir / f"{user.id}.png").exists()

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
