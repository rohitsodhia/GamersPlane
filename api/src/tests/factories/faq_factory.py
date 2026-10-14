from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import LazyAttribute, Sequence

from app.models import FAQ

from .prose import prose_doc


class FAQFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = FAQ

    category = FAQ.Categories.GETTING_STARTED
    question = Sequence(lambda n: f"Question {n}?")
    answer = LazyAttribute(lambda o: prose_doc(f"Answer to {o.question}"))
    order = Sequence(lambda n: n + 1)
