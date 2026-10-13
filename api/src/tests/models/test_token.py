from uuid import uuid4

import pytest

from app.models.token import AccountActivationToken, PasswordResetToken, Token
from tests.factories import AccountActivationTokenFactory, PasswordResetTokenFactory


class TestValidateToken:
    @pytest.mark.parametrize(
        ("factory", "token_class"),
        [
            (AccountActivationTokenFactory, AccountActivationToken),
            (PasswordResetTokenFactory, PasswordResetToken),
        ],
    )
    async def test_finds_by_token(self, create, db_session, factory, token_class):
        token = await create(factory)

        found = await Token.validate_token(db_session, str(token.token))

        assert found is not None
        assert found.id == token.id
        assert isinstance(found, token_class)

    async def test_not_found_returns_none(self, db_session):
        found = await Token.validate_token(db_session, str(uuid4()))

        assert found is None

    async def test_malformed_token_returns_none(self, db_session):
        found = await Token.validate_token(db_session, "not-a-uuid")

        assert found is None

    async def test_finds_by_token_and_matching_email(self, create, db_session):
        token = await create(AccountActivationTokenFactory)

        found = await Token.validate_token(
            db_session, str(token.token), email=token.user.email
        )

        assert found is not None
        assert found.id == token.id

    async def test_mismatched_email_returns_none(self, create, db_session):
        token = await create(AccountActivationTokenFactory)

        found = await Token.validate_token(
            db_session, str(token.token), email="wrong@example.com"
        )

        assert found is None
