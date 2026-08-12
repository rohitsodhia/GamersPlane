from __future__ import annotations

from datetime import datetime

from app.schema_base import SchemaBase


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
