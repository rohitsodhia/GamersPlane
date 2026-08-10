from __future__ import annotations

from app.models import Thread
from app.schema_base import SchemaBase


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


class GetThreads(SchemaBase):
    threads: list[ThreadData]
