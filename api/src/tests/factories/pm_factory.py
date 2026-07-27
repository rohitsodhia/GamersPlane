from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import LazyFunction, Sequence, SubFactory

from app.models import PM

from .user_factory import UserFactory


class PMFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = PM

    recipient = SubFactory(UserFactory)
    sender = SubFactory(UserFactory)
    title = Sequence(lambda n: f"PM Title {n}")
    message = Sequence(lambda n: f"PM Message {n}")
    recipient_read = False
    sender_read = False
    reply_to_id = None
    recipient_deleted = None
    sender_deleted = None
    history_ids = LazyFunction(list)
