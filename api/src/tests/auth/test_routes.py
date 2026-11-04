from datetime import datetime, timedelta, timezone

import pytest
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

    async def test_login_unactivated_user_is_told_to_activate(self, client, create):
        user = await create(UserFactory, username="unactivated", password="ValidPass1!")

        response = await client.post(
            "/auth/login",
            json={"identifier": "unactivated", "password": "ValidPass1!"},
        )

        assert response.status_code == 403
        body = response.json()
        assert body["errors"][0]["code"] == "not_activated"
        assert body["email"] == user.email
        assert "jwt" not in body
        assert user.last_activity is None

    async def test_login_unactivated_wrong_password_is_not_disclosed(
        self, client, create
    ):
        await create(UserFactory, username="unactivated", password="ValidPass1!")

        response = await client.post(
            "/auth/login",
            json={"identifier": "unactivated", "password": "WrongPass1!"},
        )

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "invalid_user"

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

    async def test_login_banned_user_is_told_they_are_banned(
        self, client, create, db_session
    ):
        user = await create(
            ActivatedUserFactory, username="bannedlogin", password="ValidPass1!"
        )
        user.banned = datetime.now(timezone.utc)
        await db_session.flush()

        response = await client.post(
            "/auth/login",
            json={"identifier": "bannedlogin", "password": "ValidPass1!"},
        )

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "banned"
        assert user.last_activity is None

    async def test_login_suspended_user_is_told_they_are_suspended(
        self, client, create, db_session
    ):
        user = await create(
            ActivatedUserFactory, username="suspendedlogin", password="ValidPass1!"
        )
        user.suspended_until = datetime.now(timezone.utc) + timedelta(days=3)
        await db_session.flush()

        response = await client.post(
            "/auth/login",
            json={"identifier": "suspendedlogin", "password": "ValidPass1!"},
        )

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "suspended"

    async def test_login_succeeds_once_suspension_has_elapsed(
        self, client, create, db_session
    ):
        user = await create(
            ActivatedUserFactory, username="unsuspended", password="ValidPass1!"
        )
        user.suspended_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db_session.flush()

        response = await client.post(
            "/auth/login",
            json={"identifier": "unsuspended", "password": "ValidPass1!"},
        )

        assert response.status_code == 200
        assert response.json()["logged_in"] is True

    async def test_login_ban_is_not_disclosed_on_wrong_password(
        self, client, create, db_session
    ):
        user = await create(
            ActivatedUserFactory, username="bannedwrong", password="ValidPass1!"
        )
        user.banned = datetime.now(timezone.utc)
        await db_session.flush()

        response = await client.post(
            "/auth/login",
            json={"identifier": "bannedwrong", "password": "WrongPass1!"},
        )

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "invalid_user"


class TestRefresh:
    async def test_refresh_returns_new_jwt(self, authed_client):
        client, _user = authed_client

        response = await client.post("/auth/refresh")

        assert response.status_code == 200
        assert response.json()["jwt"]

    async def test_refresh_rejected_for_blocked_user(self, authed_client, db_session):
        # /auth/refresh has no ban check of its own; the middleware rejects the
        # blocked user (still resolved as an identity by validate_jwt) first.
        client, user = authed_client
        user.banned = datetime.now(timezone.utc)
        await db_session.flush()

        response = await client.post("/auth/refresh")

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "banned"


class TestRegister:
    async def test_register_creates_user(self, client, db_session, site_root_forum):
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

        user = await db_session.scalar(select(User).where(User.username == "newuser"))
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


class TestResendActivation:
    async def test_resend_activation_for_existing_user(
        self, client, create, db_session
    ):
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


@pytest.fixture
def sent_emails(monkeypatch):
    sent = []

    async def fake_send_email(to, subject, content, **kwargs):
        sent.append((to, content))

    monkeypatch.setattr("app.auth.functions.send_email", fake_send_email)
    return sent


async def _reset_tokens(db_session, user):
    return (
        await db_session.scalars(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
    ).all()


class TestGeneratePasswordReset:
    async def test_activated_user_gets_token_and_email(
        self, client, create, db_session, sent_emails
    ):
        user = await create(ActivatedUserFactory)

        response = await client.post("/auth/password_reset", json={"email": user.email})

        assert response.status_code == 200
        assert response.json() == {"success": True}
        (token,) = await _reset_tokens(db_session, user)
        assert len(sent_emails) == 1
        assert sent_emails[0][0] == user.email
        assert f"/reset-password?token={token.token}" in sent_emails[0][1]

    async def test_unknown_email_looks_identical_and_sends_nothing(
        self, client, db_session, sent_emails
    ):
        response = await client.post(
            "/auth/password_reset", json={"email": "nobody@example.com"}
        )

        assert response.status_code == 200
        assert response.json() == {"success": True}
        assert sent_emails == []

    async def test_unactivated_user_looks_identical_and_gets_nothing(
        self, client, create, db_session, sent_emails
    ):
        user = await create(UserFactory)

        response = await client.post("/auth/password_reset", json={"email": user.email})

        assert response.status_code == 200
        assert response.json() == {"success": True}
        assert await _reset_tokens(db_session, user) == []
        assert sent_emails == []

    async def test_second_request_retires_the_first_token(
        self, client, create, db_session, sent_emails
    ):
        user = await create(ActivatedUserFactory)

        await client.post("/auth/password_reset", json={"email": user.email})
        await client.post("/auth/password_reset", json={"email": user.email})

        tokens = await _reset_tokens(db_session, user)
        assert len(tokens) == 2
        # Exactly one old (used) token and one new (unused) token.
        assert sorted(t.used is None for t in tokens) == [False, True]
        assert len(sent_emails) == 2


class TestCheckPasswordReset:
    async def test_valid_token(self, client, create):
        token = await create(PasswordResetTokenFactory)

        response = await client.get(
            "/auth/password_reset", params={"token": str(token.token)}
        )

        assert response.status_code == 200
        assert response.json() == {"valid_token": True}

    async def test_unknown_token(self, client):
        response = await client.get(
            "/auth/password_reset",
            params={"token": "00000000-0000-0000-0000-000000000000"},
        )

        assert response.status_code == 200
        assert response.json() == {"valid_token": False}

    async def test_used_token(self, client, create, db_session):
        token = await create(PasswordResetTokenFactory)
        token.use()
        await db_session.flush()

        response = await client.get(
            "/auth/password_reset", params={"token": str(token.token)}
        )

        assert response.json() == {"valid_token": False}

    async def test_expired_token(self, client, create, db_session):
        token = await create(PasswordResetTokenFactory)
        token.requested_on = datetime.now(timezone.utc) - PasswordResetToken.TTL * 2
        await db_session.flush()

        response = await client.get(
            "/auth/password_reset", params={"token": str(token.token)}
        )

        assert response.json() == {"valid_token": False}

    async def test_activation_token_is_not_a_reset_token(self, client, create):
        token = await create(AccountActivationTokenFactory)

        response = await client.get(
            "/auth/password_reset", params={"token": str(token.token)}
        )

        assert response.json() == {"valid_token": False}


class TestResetPassword:
    @staticmethod
    def _body(token, password="NewPass1!", confirm="NewPass1!"):
        return {
            "token": str(token.token),
            "password": password,
            "confirm_password": confirm,
        }

    async def test_success_changes_password_and_burns_token(self, client, create):
        user = await create(ActivatedUserFactory, password="OldPass1!")
        token = await create(PasswordResetTokenFactory, user=user)

        response = await client.patch("/auth/password_reset", json=self._body(token))

        assert response.status_code == 200
        assert response.json() == {"success": True}
        assert user.check_pass("NewPass1!")
        assert token.used is not None

        login = await client.post(
            "/auth/login",
            json={"identifier": user.username, "password": "NewPass1!"},
        )
        assert login.status_code == 200

        again = await client.patch(
            "/auth/password_reset", json=self._body(token, "Another1!", "Another1!")
        )
        assert again.status_code == 404
        assert again.json()["errors"][0]["code"] == "invalid_token"

    async def test_unknown_token(self, client):
        response = await client.patch(
            "/auth/password_reset",
            json={
                "token": "00000000-0000-0000-0000-000000000000",
                "password": "NewPass1!",
                "confirm_password": "NewPass1!",
            },
        )

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "invalid_token"

    async def test_mismatched_confirmation_leaves_token_usable(self, client, create):
        user = await create(ActivatedUserFactory, password="OldPass1!")
        token = await create(PasswordResetTokenFactory, user=user)

        response = await client.patch(
            "/auth/password_reset", json=self._body(token, confirm="Different1!")
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "password_mismatch"
        assert user.check_pass("OldPass1!")
        assert token.used is None
