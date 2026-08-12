from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import Sequence, SubFactory

from app.models import Post

from .prose import prose_doc
from .thread_factory import ThreadFactory
from .user_factory import UserFactory


class PostFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = Post

    thread = SubFactory(ThreadFactory)
    title = Sequence(lambda n: f"Post Title {n}")
    author = SubFactory(UserFactory)
    body = Sequence(lambda n: prose_doc(f"Post Body {n}"))
    state = Post.States.PUBLISHED
