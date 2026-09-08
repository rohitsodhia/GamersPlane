from __future__ import annotations

from app.models import Character
from app.schema_base import SchemaBase, filtered_str


class CreateCharacterInput(SchemaBase):
    label: str = filtered_str()
    character_sheet_id: int
    type: Character.Type = Character.Type.PC


class CreateCharacterResponse(SchemaBase):
    id: int
