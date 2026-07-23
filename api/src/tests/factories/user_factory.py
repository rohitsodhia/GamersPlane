from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import LazyAttribute, LazyFunction, Sequence

from app.models import User


class UserFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = User
        exclude = ["raw_password"]

    raw_password: str = "ValidPass1!"

    email = Sequence(lambda n: f"user{n}@example.com")
    display_name = Sequence(lambda n: f"user{n}")
    password = LazyAttribute(lambda o: User.hash_password(o.raw_password))
    activated_on = None


class ActivatedUserFactory(UserFactory):
    activated_on = LazyFunction(
        lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    )
