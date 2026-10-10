from __future__ import annotations

from pydantic import Field, field_validator

from app.models import Thread
from app.posts.schemas import (
    MAX_DRAWS_PER_REQUEST,
    MAX_ROLLS_PER_REQUEST,
    NewDrawInput,
    NewRollInput,
)
from app.schema_base import SchemaBase, filtered_str
from app.threads.option_schemas import ThreadOptionsUpdate, clean_discord_webhook
from app.threads.poll_schemas import PollData, PollInput


class AuthorData(SchemaBase):
    id: int
    username: str


class PostData(SchemaBase):
    id: int
    title: str
    datestamp: str
    author: AuthorData


class ThreadOptionsData(SchemaBase):
    """The thread options anyone who can read the thread may see.

    Leaves out ``discord_webhook``: the URL is a secret, as anyone holding it can
    post to the channel.
    """

    sticky: bool
    locked: bool
    allow_public_posting: bool
    allow_rolls: bool
    allow_draws: bool


class ThreadOptionsInput(Thread.Options):
    """``Thread.Options`` as submitted for a new thread.

    The webhook is only checked here, not on ``Thread.Options``, as that is
    re-validated on every load of stored data, which may hold older bad values.
    """

    @field_validator("discord_webhook")
    @classmethod
    def validate_discord_webhook(cls, value: str | None) -> str | None:
        return clean_discord_webhook(value)


class ThreadData(SchemaBase):
    id: int
    first_post: PostData
    last_post: PostData
    options: ThreadOptionsData
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
    options: ThreadOptionsData
    first_post_id: int
    # The earliest post the principal hasn't read and the page it's on; both
    # null for guests and when the thread is fully read.
    first_unread_post_id: int | None
    first_unread_page: int | None
    # The principal's verbs on the thread's forum.
    permissions: list[str]
    poll: PollData | None = None


class MarkThreadViewedInput(SchemaBase):
    # The last post shown on the page the principal just viewed.
    post_id: int


class NewThreadInput(SchemaBase):
    forum_id: int
    title: str = filtered_str()
    body: dict
    posted_as_id: int | None = None
    options: ThreadOptionsInput = ThreadOptionsInput()
    rolls: list[NewRollInput] = Field(default=[], max_length=MAX_ROLLS_PER_REQUEST)
    draws: list[NewDrawInput] = Field(default=[], max_length=MAX_DRAWS_PER_REQUEST)
    poll: PollInput | None = None


class UpdateThreadInput(SchemaBase):
    options: ThreadOptionsUpdate


class NewThreadResponse(SchemaBase):
    id: int
