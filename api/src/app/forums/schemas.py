from models import Forum
from pydantic import BaseModel


class CreateForumInput(BaseModel):
    title: str
    forumType: Forum.ForumTypes
    parent: int
    gameId: int | None = None
    description: str | None = None


class UpdateForumInput(BaseModel):
    title: str | None = None
    forumType: Forum.ForumTypes | None = None
    parent: int | None = None
    gameId: int | None = None
    description: str | None = None
    order: int | None = None
