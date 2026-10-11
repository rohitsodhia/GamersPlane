from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from app.schema_base import SchemaBase

# Trimmed before the length check, so a blank name is rejected.
NPCName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class GameImageData(SchemaBase):
    id: int
    url: str


class LinkImageInput(SchemaBase):
    url: str


class NPCData(SchemaBase):
    id: int
    name: str
    image: GameImageData | None
    last_used_at: datetime | None


class UpdateNPCInput(SchemaBase):
    # Absent leaves a field alone; image_id may be null to drop the image.
    name: NPCName | None = None
    image_id: int | None = None


class PostedNPCInput(SchemaBase):
    """A quick NPC to post as; the matching name + image pair is found or made."""

    name: NPCName
    image_id: int | None = None
