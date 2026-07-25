from uuid import uuid4

from app.models.token import AccountActivationToken, PasswordResetToken, Token
from tests.factories import AccountActivationTokenFactory, PasswordResetTokenFactory


class TestValidateToken:
    async def test_finds_by_token(self, create, db_session):
        token = await create(AccountActivationTokenFactory)

        found = await Token.validate_token(db_session, str(token.token))

        assert found is not None
        assert found.id == token.id

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


class TestUse:
    async def test_sets_used_timestamp(self, create):
        token = await create(AccountActivationTokenFactory)
        assert token.used is None

        token.use()

        assert token.used is not None


class TestPolymorphicIdentity:
    async def test_account_activation_token_type(self, create, db_session):
        token = await create(AccountActivationTokenFactory)
        await db_session.flush()

        found = await Token.validate_token(db_session, str(token.token))

        assert isinstance(found, AccountActivationToken)

    async def test_password_reset_token_type(self, create, db_session):
        token = await create(PasswordResetTokenFactory)
        await db_session.flush()

        found = await Token.validate_token(db_session, str(token.token))

        assert isinstance(found, PasswordResetToken)
