import pytest
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
    @pytest.mark.parametrize(
        ("password", "confirm", "expected_codes"),
        [
            pytest.param("ValidPass1!", "ValidPass1!", [], id="matching_valid"),
            pytest.param(
                "ValidPass1!", "Different1!", ["password_mismatch"], id="mismatched"
            ),
            pytest.param("short", "short", ["invalid_password"], id="too_short"),
            pytest.param(
                "short",
                "other",
                ["password_mismatch", "invalid_password"],
                id="mismatched_and_too_short",
            ),
        ],
    )
    def test_validate_password_change(self, password, confirm, expected_codes):
        errors = validate_password_change(password, confirm)

        assert [e.code for e in errors] == expected_codes


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
        assert link == f"{configs.HOST_NAME}/activate?token={token.token}"

    async def test_reuses_existing_token(self, db_session, create):
        user = await create(UserFactory)
        existing_token = await create(AccountActivationTokenFactory, user=user)

        link = await get_activation_link(db_session, user)

        assert link == f"{configs.HOST_NAME}/activate?token={existing_token.token}"


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
