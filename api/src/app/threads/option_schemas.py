"""Thread option schemas that ``app.posts.schemas`` also needs.

Kept apart from ``app.threads.schemas``, which imports from ``app.posts.schemas``.
"""

from __future__ import annotations

import re

from pydantic import ConfigDict, field_validator

from app.schema_base import SchemaBase

DISCORD_WEBHOOK_PATTERN = re.compile(
    r"https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/(?:v\d+/)?webhooks/\d+/[A-Za-z0-9_-]+"
)


def clean_discord_webhook(value: str | None) -> str | None:
    """Strip a submitted webhook, treating blank as unset; raise if it isn't a
    Discord webhook URL."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not DISCORD_WEBHOOK_PATTERN.fullmatch(value):
        raise ValueError(
            "Discord webhook must be a Discord webhook URL "
            "(https://discord.com/api/webhooks/…)"
        )
    return value


class ThreadOptionsUpdate(SchemaBase):
    """A partial change to a thread's options.

    Only the fields actually sent are applied. A boolean sent as ``null`` counts
    as not sent; ``discord_webhook`` sent as ``null`` or ``""`` clears it.
    """

    model_config = ConfigDict(extra="forbid")

    sticky: bool | None = None
    locked: bool | None = None
    allow_public_posting: bool | None = None
    allow_rolls: bool | None = None
    allow_draws: bool | None = None
    discord_webhook: str | None = None

    @field_validator("discord_webhook")
    @classmethod
    def validate_discord_webhook(cls, value: str | None) -> str | None:
        return clean_discord_webhook(value)
