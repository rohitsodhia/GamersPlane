from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import Sequence

from app.models import Publisher


class PublisherFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = Publisher

    name = Sequence(lambda n: f"Publisher {n}")
    website = None
