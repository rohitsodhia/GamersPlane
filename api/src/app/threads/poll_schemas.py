from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from app.schema_base import SchemaBase

MAX_POLL_TEXT_LENGTH = 200
MIN_POLL_OPTIONS = 2
MAX_POLL_OPTIONS = 25


def _trimmed(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


class PollOptionInput(SchemaBase):
    # Set on edit to keep an existing option (and its votes); omit for a new one.
    id: int | None = None
    text: str = Field(min_length=1, max_length=MAX_POLL_TEXT_LENGTH)

    _trim_text = field_validator("text", mode="before")(_trimmed)


class PollInput(SchemaBase):
    """A poll as submitted, for both creating and editing. Options are in display
    order."""

    question: str = Field(min_length=1, max_length=MAX_POLL_TEXT_LENGTH)
    options_per_user: int = Field(ge=1)
    allow_revoting: bool
    options: list[PollOptionInput] = Field(
        min_length=MIN_POLL_OPTIONS, max_length=MAX_POLL_OPTIONS
    )

    _trim_question = field_validator("question", mode="before")(_trimmed)

    @model_validator(mode="after")
    def validate_options(self) -> PollInput:
        texts = [option.text.casefold() for option in self.options]
        if len(set(texts)) != len(texts):
            raise ValueError("Poll options must be different from each other")
        ids = [option.id for option in self.options if option.id is not None]
        if len(set(ids)) != len(ids):
            raise ValueError("An option can only be listed once")
        if self.options_per_user > len(self.options):
            raise ValueError("options_per_user can't exceed the number of options")
        return self


class PollOptionData(SchemaBase):
    id: int
    text: str
    # None while the viewer can't see results.
    votes: int | None


class PollData(SchemaBase):
    question: str
    options_per_user: int
    allow_revoting: bool
    options: list[PollOptionData]
    # The option ids the viewer voted for.
    my_votes: list[int]
    voted: bool
    can_vote: bool
    show_results: bool
    # How many people have voted; None while results are hidden.
    total_voters: int | None


class VoteInput(SchemaBase):
    option_ids: list[int]
