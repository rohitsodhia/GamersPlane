from __future__ import annotations

from app.models import Thread
from app.schema_base import SchemaBase, filtered_str


class AuthorData(SchemaBase):
    id: int
    username: str


class PostData(SchemaBase):
    id: int
    title: str
    datestamp: str
    author: AuthorData


class ThreadData(SchemaBase):
    id: int
    first_post: PostData
    last_post: PostData
    options: Thread.Options
    post_count: int


class GetThreadsResponse(SchemaBase):
    threads: list[ThreadData]
    count: int
    page: int


class GetThreadResponse(SchemaBase):
    id: int
    forum_id: int
    title: str
    options: Thread.Options


class NewThreadInput(SchemaBase):
    forum_id: int
    title: str = filtered_str()
    body: dict
    options: Thread.Options = Thread.Options()


class NewThreadResponse(SchemaBase):
    id: int
