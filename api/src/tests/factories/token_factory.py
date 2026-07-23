from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import SubFactory

from app.models.token import AccountActivationToken, PasswordResetToken

from .user_factory import ActivatedUserFactory, UserFactory


class AccountActivationTokenFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = AccountActivationToken

    user = SubFactory(UserFactory)


class PasswordResetTokenFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = PasswordResetToken

    user = SubFactory(ActivatedUserFactory)
