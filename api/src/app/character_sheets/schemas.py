from __future__ import annotations

from app.models import CharacterSheet
from app.schema_base import SchemaBase, filtered_str


class UserData(SchemaBase):
    id: int
    username: str
    avatar: str


class SystemData(SchemaBase):
    id: str
    name: str


class CreateCharSheetInput(SchemaBase):
    name: str = filtered_str()
    system_id: str


class CreateCharSheetResponse(SchemaBase):
    id: int


class BasicCharSheetData(SchemaBase):
    id: int
    name: str
    creator: UserData
    system: SystemData
    favorited: bool


class GetMyCharSheetsResponse(SchemaBase):
    char_sheets: list[BasicCharSheetData]


class UpdateCharSheetInput(SchemaBase):
    layout: dict


class GetCharSheetResponse(SchemaBase):
    id: int
    creator: UserData
    root_id: int | None = None
    name: str
    system: SystemData
    layout: dict
    status: CharacterSheet.Status
