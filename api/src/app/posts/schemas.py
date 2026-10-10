from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schema_base import SchemaBase, filtered_str, strip_whitespace
from app.threads.option_schemas import ThreadOptionsUpdate

RollSystem = Literal["basic", "fate", "fengshui", "starwarsffg"]

MAX_ROLLS_PER_REQUEST = 10
MAX_DRAWS_PER_REQUEST = 10


class AuthorData(SchemaBase):
    id: int
    username: str
    avatar: str


class PostRollData(SchemaBase):
    """A roll as one viewer may see it. ``None`` means withheld from this viewer.

    The three ``hide_*`` flags are always sent. See ``redact_roll`` for exactly
    what each one withholds.
    """

    id: int
    type: RollSystem
    reason: str | None
    input: str | None
    options: dict | None
    # The full ``RollResult`` dump.
    result: dict | None
    # Only the total-ish values (no faces), sent instead of ``result`` when the dice
    # are hidden but the result isn't.
    summary: dict | None
    hide_reason: bool
    hide_dice: bool
    hide_result: bool


class PostDrawData(SchemaBase):
    """A draw as one viewer may see it. Unrevealed cards are ``None`` unless the
    viewer is the author; the list keeps its length so the UI can show card backs."""

    id: int
    deck_id: int | None
    deck_label: str
    deck_type: str
    reason: str
    cards: list[int | None]
    revealed: list[bool]


class PostData(SchemaBase):
    id: int
    title: str
    datestamp: datetime
    author: AuthorData
    body: dict
    rolls: list[PostRollData] = []
    draws: list[PostDrawData] = []


class GetPostResponse(PostData):
    datestamp: datetime | None
    is_first_post: bool = False
    # The thread's Discord webhook; only sent to the author of the first post, who
    # can edit it. Null for everyone else.
    discord_webhook: str | None = None
    thread_id: int
    forum_id: int
    page: int


class GetPostsResponse(SchemaBase):
    posts: list[PostData]
    count: int
    page: int


class NewRollOptions(SchemaBase):
    # Each system only reads its own option; the rest are ignored.
    reroll_aces: bool = False  # basic
    modifier: int = 0  # fate
    roll_type: Literal["standard", "fortune", "closed"] = "standard"  # fengshui


class NewRollInput(SchemaBase):
    type: RollSystem
    roll: str = Field(min_length=1)
    reason: str = filtered_str(pipelines=[strip_whitespace], default="", max_length=100)
    options: NewRollOptions = NewRollOptions()
    hide_reason: bool = False
    hide_dice: bool = False
    hide_result: bool = False


class NewDrawInput(SchemaBase):
    deck_id: int
    count: int = Field(ge=1)
    reason: str = filtered_str(
        pipelines=[strip_whitespace], min_length=1, max_length=100
    )


class RollVisibilityInput(SchemaBase):
    id: int
    hide_reason: bool
    hide_dice: bool
    hide_result: bool


class NewPostInput(SchemaBase):
    thread_id: int
    title: str = filtered_str()
    body: dict
    rolls: list[NewRollInput] = Field(default=[], max_length=MAX_ROLLS_PER_REQUEST)
    draws: list[NewDrawInput] = Field(default=[], max_length=MAX_DRAWS_PER_REQUEST)


class NewPostResponse(SchemaBase):
    id: int


class EditPostInput(SchemaBase):
    title: str = filtered_str()
    body: dict
    # New rolls/draws to attach; existing ones are never touched by an edit.
    rolls: list[NewRollInput] = Field(default=[], max_length=MAX_ROLLS_PER_REQUEST)
    draws: list[NewDrawInput] = Field(default=[], max_length=MAX_DRAWS_PER_REQUEST)
    # Visibility changes for rolls already on the post.
    roll_visibility: list[RollVisibilityInput] = []
    # Changes to the thread's options; only accepted when editing its first post.
    thread_options: ThreadOptionsUpdate | None = None
    # Not stored; a minor edit just skips the Discord ping.
    minor_edit: bool = False


class EditPostResponse(SchemaBase):
    id: int
