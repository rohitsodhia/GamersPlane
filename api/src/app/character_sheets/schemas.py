from __future__ import annotations

from app.models import CharacterSheet
from app.schema_base import SchemaBase, filtered_str


class CreateCharSheetInput(SchemaBase):
    name: str = filtered_str()
    system_id: str


class CreateCharSheetResponse(SchemaBase):
    id: int


class UpdateCharSheetInput(SchemaBase):
    layout: dict


class UserData(SchemaBase):
    id: int
    username: str
    avatar: str


class SystemData(SchemaBase):
    id: str
    name: str


class GetCharSheetResponse(SchemaBase):
    id: int
    creator: UserData
    root_id: int | None = None
    name: str
    system: SystemData
    layout: dict
    status: CharacterSheet.Status
