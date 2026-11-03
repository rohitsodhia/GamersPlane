from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from app.schema_base import SchemaBase


class NotificationActor(SchemaBase):
    id: int
    username: str


class NotificationBase(SchemaBase):
    eventId: int
    actor: NotificationActor
    createdAt: datetime
    read: bool


class MentionNotification(NotificationBase):
    type: Literal["mention"] = "mention"
    threadId: int
    threadTitle: str
    postId: int
    forumId: int


class GameInviteNotification(NotificationBase):
    """The actor is the GM who invited the user."""

    type: Literal["game_invite"] = "game_invite"
    gameId: int
    gameTitle: str


class GameApplicationNotification(NotificationBase):
    """The actor is the applicant."""

    type: Literal["game_application"] = "game_application"
    gameId: int
    gameTitle: str


class CharacterSubmittedNotification(NotificationBase):
    """The actor is the character's owner."""

    type: Literal["character_submitted"] = "character_submitted"
    gameId: int
    gameTitle: str
    characterId: int
    characterName: str


Notification = Annotated[
    MentionNotification
    | GameInviteNotification
    | GameApplicationNotification
    | CharacterSubmittedNotification,
    Field(discriminator="type"),
]
