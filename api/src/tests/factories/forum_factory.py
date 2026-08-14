from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import LazyFunction, Sequence

from app.models import Forum


class ForumFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = Forum

    title = Sequence(lambda n: f"Forum {n}")
    description = None
    forum_type = Forum.ForumTypes.FORUM
    parent_id = None
    heritage = LazyFunction(list)
    order = Sequence(lambda n: n)
    game_id = None
    thread_count = 0
