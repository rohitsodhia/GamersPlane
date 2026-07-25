from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import Sequence, SubFactory

from app.models import Role

from .user_factory import UserFactory


class RoleFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = Role

    name = Sequence(lambda n: f"Role {n}")
    owner = SubFactory(UserFactory)
