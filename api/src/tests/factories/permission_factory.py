from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import Sequence

from app.models import Permission


class PermissionFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = Permission

    permission = Sequence(lambda n: f"permission_{n}")
