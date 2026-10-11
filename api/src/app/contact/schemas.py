from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, EmailStr, StringConstraints

from app.schema_base import SchemaBase

NAME_MAX = 50
EMAIL_MAX = 100
USERNAME_MAX = 50
SUBJECT_MAX = 100
MESSAGE_MAX = 5000


def _strip(v: object) -> object:
    return v.strip() if isinstance(v, str) else v


def _single_line(v: str) -> str:
    """Reject CR/LF so the value can't smuggle extra headers into the email."""
    if "\r" in v or "\n" in v:
        raise ValueError("Must be a single line")
    return v


def _email_max_length(v: str) -> str:
    if len(v) > EMAIL_MAX:
        raise ValueError(f"Must be at most {EMAIL_MAX} characters")
    return v


Name = Annotated[
    str,
    BeforeValidator(_strip),
    StringConstraints(min_length=1, max_length=NAME_MAX),
    AfterValidator(_single_line),
]
Email = Annotated[EmailStr, BeforeValidator(_strip), AfterValidator(_email_max_length)]
Username = Annotated[
    str,
    BeforeValidator(_strip),
    StringConstraints(max_length=USERNAME_MAX),
    AfterValidator(_single_line),
]
Subject = Annotated[
    str,
    BeforeValidator(_strip),
    StringConstraints(min_length=1, max_length=SUBJECT_MAX),
    AfterValidator(_single_line),
]
Message = Annotated[
    str,
    BeforeValidator(_strip),
    StringConstraints(min_length=1, max_length=MESSAGE_MAX),
]


class ContactInput(SchemaBase):
    name: Name
    email: Email
    # Only meaningful for logged-out visitors; the route ignores it otherwise.
    username: Username = ""
    subject: Subject
    message: Message
    # Honeypot: hidden from humans in the form, so anything in it means a bot.
    website: str | None = None
