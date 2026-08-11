from __future__ import annotations

from app.models import Thread
from app.schema_base import SchemaBase, filtered_str


class AuthorData(SchemaBase):
    id: int
    name: str


class PostData(SchemaBase):
    id: int
    title: str
    datestamp: str
    author: AuthorData


class ThreadData(SchemaBase):
    id: int
    title: str
    first_post: PostData
    last_post: PostData
    options: list[Thread.ThreadOptions]
    post_count: int


class GetThreadsResponse(SchemaBase):
    threads: list[ThreadData]
    count: int
    page: int


class NewThreadInput(SchemaBase):
    forum_id: int
    title: str = filtered_str()
    body: dict
    options: list[Thread.ThreadOptions]


class NewThreadResponse(SchemaBase):
    id: int
