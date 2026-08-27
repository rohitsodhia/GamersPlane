from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import Sequence

from app.models import DeckType


class DeckTypeFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = DeckType

    short = Sequence(lambda n: f"dt{n}")
    name = Sequence(lambda n: f"Deck Type {n}")
    deck_size = 52
