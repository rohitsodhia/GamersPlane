from sqlalchemy import select

from app.auth.functions import (
    activate_account,
    get_activation_link,
    validate_password_change,
)
from app.configs import configs
from app.models import AccountActivationToken
from tests.factories import AccountActivationTokenFactory, UserFactory


class TestValidatePasswordChange:
    def test_matching_valid_passwords_has_no_errors(self):
        errors = validate_password_change("ValidPass1!", "ValidPass1!")

        assert errors == []

    def test_mismatched_passwords_returns_error(self):
        errors = validate_password_change("ValidPass1!", "Different1!")

        assert [e.code for e in errors] == ["password_mismatch"]

    def test_too_short_password_returns_error(self):
        errors = validate_password_change("short", "short")

        assert [e.code for e in errors] == ["invalid_password"]

    def test_mismatched_and_too_short_returns_both_errors(self):
        errors = validate_password_change("short", "other")

        assert [e.code for e in errors] == ["password_mismatch", "invalid_password"]


class TestGetActivationLink:
    async def test_creates_token_when_none_exists(self, db_session, create):
        user = await create(UserFactory)

        link = await get_activation_link(db_session, user)

        token = await db_session.scalar(
            select(AccountActivationToken).where(
                AccountActivationToken.user_id == user.id
            )
        )
        assert token is not None
        assert link == f"{configs.HOST_NAME}/activate/{token.token}"

    async def test_reuses_existing_token(self, db_session, create):
        user = await create(UserFactory)
        existing_token = await create(AccountActivationTokenFactory, user=user)

        link = await get_activation_link(db_session, user)

        assert link == f"{configs.HOST_NAME}/activate/{existing_token.token}"


class TestActivateAccount:
    async def test_valid_token_activates_user(self, db_session, create):
        user = await create(UserFactory)
        token = await create(AccountActivationTokenFactory, user=user)

        activated = await activate_account(db_session, str(token.token))

        assert activated is True
        assert user.activated_on is not None
        assert token.used is not None

    async def test_invalid_token_returns_false(self, db_session):
        activated = await activate_account(
            db_session, "00000000-0000-0000-0000-000000000000"
        )

        assert activated is False
