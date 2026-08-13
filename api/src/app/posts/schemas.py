from __future__ import annotations

from datetime import datetime

from app.schema_base import SchemaBase, filtered_str


class AuthorData(SchemaBase):
    id: int
    username: str
    avatar: str


class PostData(SchemaBase):
    id: int
    title: str
    datestamp: datetime
    author: AuthorData
    body: dict


class GetPostsResponse(SchemaBase):
    posts: list[PostData]
    count: int
    page: int


class NewPostInput(SchemaBase):
    thread_id: int
    title: str = filtered_str()
    body: dict


class NewPostResponse(SchemaBase):
    id: int


class EditPostInput(SchemaBase):
    title: str = filtered_str()
    body: dict


class EditPostResponse(SchemaBase):
    id: int
