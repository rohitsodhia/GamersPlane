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
    # Whether the principal has unread posts here. Always false for guests.
    has_unread: bool


class GetThreadsResponse(SchemaBase):
    threads: list[ThreadData]
    count: int
    page: int


class GetThreadResponse(SchemaBase):
    id: int
    forum_id: int
    title: str
    options: Thread.Options
    first_post_id: int
    # The earliest post the principal hasn't read and the page it's on; both
    # null for guests and when the thread is fully read.
    first_unread_post_id: int | None
    first_unread_page: int | None
    # The principal's verbs on the thread's forum.
    permissions: list[str]


class MarkThreadViewedInput(SchemaBase):
    # The last post shown on the page the principal just viewed.
    post_id: int


class NewThreadInput(SchemaBase):
    forum_id: int
    title: str = filtered_str()
    body: dict
    options: Thread.Options = Thread.Options()


class NewThreadResponse(SchemaBase):
    id: int
