from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import LazyFunction, SubFactory

from app.models import Thread

from .forum_factory import ForumFactory


class ThreadFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = Thread

    forum = SubFactory(ForumFactory, heritage=[])
    options = LazyFunction(Thread.Options)
    post_count = 0
