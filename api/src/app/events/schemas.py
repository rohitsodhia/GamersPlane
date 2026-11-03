from datetime import datetime

from app.schema_base import SchemaBase


class MentionActor(SchemaBase):
    id: int
    username: str


class MentionItem(SchemaBase):
    eventId: int
    actor: MentionActor
    threadId: int
    threadTitle: str
    postId: int
    forumId: int
    createdAt: datetime
    read: bool
