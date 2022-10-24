from lib2to3.pgen2.token import OP
from typing import Optional

from pydantic import BaseModel, create_model

from forums.models.forum import Forum
from permissions.models.permission import ForumPermissions


PermissionsDict = create_model(
    "PermissionsDict",
    **{permission.value: (bool, False) for permission in ForumPermissions}
)


class CreateForumInput(BaseModel):
    title: str
    forumType: Forum.ForumTypes
    parent: int
    gameId: Optional[int] = None
    description: Optional[str] = None


class UpdateForumInput(BaseModel):
    title: Optional[str] = None
    forumType: Optional[Forum.ForumTypes] = None
    parent: Optional[int] = None
    gameId: Optional[int] = None
    description: Optional[str] = None
    order: Optional[int] = None
