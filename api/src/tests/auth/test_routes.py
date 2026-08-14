from sqlalchemy import select

from app.models import AccountActivationToken, PasswordResetToken, User
from tests.factories import (
    AccountActivationTokenFactory,
    ActivatedUserFactory,
    PasswordResetTokenFactory,
    UserFactory,
)


class TestLogin:
    async def test_login_with_username(self, client, create):
        user = await create(
            ActivatedUserFactory, username="loginuser", password="ValidPass1!"
        )

        response = await client.post(
            "/auth/login",
            json={"identifier": "loginuser", "password": "ValidPass1!"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["logged_in"] is True
        assert body["jwt"]
        assert body["user"] == {"username": "loginuser", "email": user.email}

    async def test_login_with_email(self, client, create):
        user = await create(ActivatedUserFactory, password="ValidPass1!")

        response = await client.post(
            "/auth/login",
            json={"identifier": user.email, "password": "ValidPass1!"},
        )

        assert response.status_code == 200
        assert response.json()["logged_in"] is True

    async def test_login_wrong_password(self, client, create):
        await create(ActivatedUserFactory, username="wrongpass", password="ValidPass1!")

        response = await client.post(
            "/auth/login",
            json={"identifier": "wrongpass", "password": "WrongPass1!"},
        )

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "invalid_user"

    async def test_login_unknown_user(self, client):
        response = await client.post(
            "/auth/login",
            json={"identifier": "nobody", "password": "ValidPass1!"},
        )

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "invalid_user"

    async def test_login_unactivated_user(self, client, create):
        await create(UserFactory, username="unactivated", password="ValidPass1!")

        response = await client.post(
            "/auth/login",
            json={"identifier": "unactivated", "password": "ValidPass1!"},
        )

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "invalid_user"

    async def test_login_password_too_short_is_rejected(self, client):
        response = await client.post(
            "/auth/login",
            json={"identifier": "someone", "password": "short"},
        )

        assert response.status_code == 422

    async def test_login_updates_last_activity(self, client, create):
        user = await create(
            ActivatedUserFactory, username="loginuser", password="ValidPass1!"
        )
        assert user.last_activity is None

        response = await client.post(
            "/auth/login",
            json={"identifier": "loginuser", "password": "ValidPass1!"},
        )

        assert response.status_code == 200
        assert user.last_activity is not None

    async def test_login_wrong_password_does_not_update_last_activity(
        self, client, create
    ):
        user = await create(
            ActivatedUserFactory, username="wrongpass", password="ValidPass1!"
        )

        response = await client.post(
            "/auth/login",
            json={"identifier": "wrongpass", "password": "WrongPass1!"},
        )

        assert response.status_code == 404
        assert user.last_activity is None


class TestRefresh:
    async def test_refresh_requires_auth(self, client):
        response = await client.post("/auth/refresh")

        assert response.status_code == 403

    async def test_refresh_returns_new_jwt(self, authed_client):
        client, _user = authed_client

        response = await client.post("/auth/refresh")

        assert response.status_code == 200
        assert response.json()["jwt"]


class TestRegister:
    async def test_register_creates_user(self, client, db_session):
        response = await client.post(
            "/auth/register",
            json={
                "identifier": "newuser",
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "ValidPass1!",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"registered": True}

        user = await db_session.scalar(
            select(User).where(User.username == "newuser")
        )
        assert user is not None
        assert user.activated_on is None

        token = await db_session.scalar(
            select(AccountActivationToken).where(
                AccountActivationToken.user_id == user.id
            )
        )
        assert token is not None

    async def test_register_existing_user_returns_errors(self, client, create):
        existing = await create(UserFactory)

        response = await client.post(
            "/auth/register",
            json={
                "email": existing.email,
                "username": "another",
                "password": "ValidPass1!",
            },
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "email_taken"

    async def test_register_invalid_username_is_rejected(self, client):
        response = await client.post(
            "/auth/register",
            json={
                "email": "another@example.com",
                "username": "1another",
                "password": "ValidPass1!",
            },
        )

        assert response.status_code == 422

    async def test_register_password_too_short(self, client):
        response = await client.post(
            "/auth/register",
            json={
                "email": "another@example.com",
                "username": "another",
                "password": "short",
            },
        )

        assert response.status_code == 422


class TestResendActivation:
    async def test_resend_activation_for_existing_user(self, client, create, db_session):
        user = await create(UserFactory)

        response = await client.post(
            "/auth/resendActivation", json={"email": user.email}
        )

        assert response.status_code == 200
        assert response.json() == {"success": True}

        token = await db_session.scalar(
            select(AccountActivationToken).where(
                AccountActivationToken.user_id == user.id
            )
        )
        assert token is not None

    async def test_resend_activation_for_unknown_email_still_succeeds(self, client):
        response = await client.post(
            "/auth/resendActivation", json={"email": "nobody@example.com"}
        )

        assert response.status_code == 200
        assert response.json() == {"success": True}


class TestActivateUser:
    async def test_activate_with_valid_token(self, client, create):
        user = await create(UserFactory)
        token = await create(AccountActivationTokenFactory, user=user)

        response = await client.post(f"/auth/activate/{token.token}")

        assert response.status_code == 200
        assert response.json() == {"success": True}

    async def test_activate_with_invalid_token(self, client):
        response = await client.post(
            "/auth/activate/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "invalid_token"


class TestGeneratePasswordReset:
    async def test_generate_for_existing_user(self, client, create, db_session):
        user = await create(ActivatedUserFactory)

        response = await client.post("/auth/password_reset", json={"email": user.email})

        assert response.status_code == 200
        assert response.json() == {"success": True}

        token = await db_session.scalar(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
        assert token is not None

    async def test_generate_for_unknown_email(self, client):
        response = await client.post(
            "/auth/password_reset", json={"email": "nobody@example.com"}
        )

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "no_account"


class TestCheckPasswordReset:
    async def test_valid_token(self, client, create):
        user = await create(ActivatedUserFactory)
        token = await create(PasswordResetTokenFactory, user=user)

        response = await client.get(
            "/auth/password_reset",
            params={"email": user.email, "token": str(token.token)},
        )

        assert response.status_code == 200
        assert response.json() == {"valid_token": True}

    async def test_invalid_token(self, client, create):
        user = await create(ActivatedUserFactory)

        response = await client.get(
            "/auth/password_reset",
            params={
                "email": user.email,
                "token": "00000000-0000-0000-0000-000000000000",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"valid_token": False}


class TestResetPassword:
    async def test_reset_password_success(self, client, create):
        user = await create(ActivatedUserFactory, password="OldPass1!")
        token = await create(PasswordResetTokenFactory, user=user)

        response = await client.patch(
            "/auth/password_reset",
            json={
                "email": user.email,
                "token": str(token.token),
                "password": "NewPass1!",
                "confirm_password": "NewPass1!",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"success": True}

        assert user.check_pass("NewPass1!")
        assert token.used is not None

    async def test_reset_password_mismatched_confirmation(self, client, create):
        user = await create(ActivatedUserFactory)
        token = await create(PasswordResetTokenFactory, user=user)

        response = await client.patch(
            "/auth/password_reset",
            json={
                "email": user.email,
                "token": str(token.token),
                "password": "NewPass1!",
                "confirm_password": "Different1!",
            },
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "password_mismatch"

    async def test_reset_password_invalid_token(self, client, create):
        user = await create(ActivatedUserFactory)

        response = await client.patch(
            "/auth/password_reset",
            json={
                "email": user.email,
                "token": "00000000-0000-0000-0000-000000000000",
                "password": "NewPass1!",
                "confirm_password": "NewPass1!",
            },
        )

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "invalid_token"
