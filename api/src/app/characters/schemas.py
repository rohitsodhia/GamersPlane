from __future__ import annotations

from app.models import Character
from app.schema_base import SchemaBase, filtered_str


class SystemData(SchemaBase):
    id: str
    name: str


class UserData(SchemaBase):
    id: int
    username: str
    avatar: str


class CreateCharacterInput(SchemaBase):
    label: str = filtered_str()
    character_sheet_id: int
    type: Character.Type = Character.Type.PC


class CreateCharacterResponse(SchemaBase):
    id: int


class UpdateCharacterInput(SchemaBase):
    values: dict


class CharacterSheetData(SchemaBase):
    id: int
    name: str
    creator: UserData
    system: SystemData
    layout: dict


class GetCharacterResponse(SchemaBase):
    id: int
    label: str
    name: str | None = None
    type: Character.Type
    values: dict | None = None
    character_sheet: CharacterSheetData
