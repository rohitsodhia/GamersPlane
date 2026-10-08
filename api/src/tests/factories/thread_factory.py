from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import LazyFunction, SubFactory

from app.models import Thread

from .forum_factory import ForumFactory


class ThreadFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = Thread

    # Under the site root (forum 0), like every real forum, so a grant on 0
    # reaches it. Forum 0's row needn't exist; the resolver only uses the id.
    forum = SubFactory(ForumFactory, heritage=[0])
    options = LazyFunction(Thread.Options)
    post_count = 0
