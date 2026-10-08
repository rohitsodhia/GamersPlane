from __future__ import annotations

from app.models.forum import Forum
from app.schema_base import SchemaBase


class HeritageForumData(SchemaBase):
    id: int
    title: str


class AuthorData(SchemaBase):
    id: int
    username: str


class LastPostDetails(SchemaBase):
    id: int
    title: str
    datestamp: str
    author: AuthorData


class ChildForumData(SchemaBase):
    id: int
    title: str
    description: str | None
    forum_type: Forum.ForumTypes
    parent_id: int | None
    order: int
    thread_count: int
    post_count: int
    last_post: LastPostDetails | None
    children: list[ChildForumData] = []


ChildForumData.model_rebuild()


class ModeratedForumData(SchemaBase):
    id: int
    title: str
    # False for a forum listed only as a heading over forums the principal
    # moderates.
    moderate: bool
    children: list[ModeratedForumData] = []


ModeratedForumData.model_rebuild()


class GetForumBreadcrumbsResponse(SchemaBase):
    id: int
    title: str
    heritage: list[HeritageForumData]


class GetForum(SchemaBase):
    id: int
    title: str
    description: str | None
    forum_type: Forum.ForumTypes
    parent_id: int | None
    heritage: list[HeritageForumData]
    order: int
    game_id: int | None
    thread_count: int
    # Forum verbs the principal holds here. A forum shown only because it has
    # readable subforums lacks forum_read, and has no threads to list.
    permissions: list[str]
    children: list[ChildForumData] = []
