from factories.user_factory import UserFactory
from tokens.models import Token, AccountActivationToken
from users.models import User


class TestToken:
    def test_save(self):
        user = UserFactory()
        user.save()
        token = AccountActivationToken(user=user)
        token.save()
        assert token.token_type == Token.TokenTypes.ACCOUNT_ACTIVATION.value
