import factory
from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import Sequence

from app.models import User


class UserFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = User

    username = Sequence(lambda n: f"user{n}")
    email = Sequence(lambda n: f"user{n}@example.com")

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        obj.set_password(extracted or "ValidPass1!")


class ActivatedUserFactory(UserFactory):
    @factory.post_generation
    def activated_on(obj, create, extracted, **kwargs):
        obj.activate()
