from factories.user_factory import UserFactory
from tokens.models import AccountActivationToken, Token


class TestToken:
    def test_save(self):
        user = UserFactory()
        user.save()
        token = AccountActivationToken(user=user)
        token.save()
        assert token.token_type == Token.TokenTypes.ACCOUNT_ACTIVATION.value
