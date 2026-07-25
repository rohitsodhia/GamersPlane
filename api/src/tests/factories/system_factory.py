from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import LazyFunction, Sequence, SubFactory

from app.models import System

from .publisher_factory import PublisherFactory


class SystemFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = System

    id = Sequence(lambda n: f"system{n}")
    name = Sequence(lambda n: f"System {n}")
    sort_name = Sequence(lambda n: f"System {n}")
    publisher = SubFactory(PublisherFactory)
    genres = LazyFunction(list)
    basics = LazyFunction(list)
    has_char_sheet = False
    enabled = True
