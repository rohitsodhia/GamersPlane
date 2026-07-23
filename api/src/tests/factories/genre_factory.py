from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import Sequence

from app.models import Genre


class GenreFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = Genre

    genre = Sequence(lambda n: f"Genre {n}")
