from __future__ import annotations

from app.models import CharacterSheet
from app.schema_base import SchemaBase, filtered_str


class UserData(SchemaBase):
    id: int
    username: str


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
    description: dict | None
    favorited: bool


class GetMyCharSheetsResponse(SchemaBase):
    char_sheets: list[BasicCharSheetData]
    total: int
    page: int


class LibraryUserData(SchemaBase):
    id: int
    username: str


class LibraryCharSheetData(SchemaBase):
    id: int
    name: str
    system: SystemData
    creator: LibraryUserData
    description: dict | None
    status: CharacterSheet.Status
    favorited: bool


class GetLibraryResponse(SchemaBase):
    char_sheets: list[LibraryCharSheetData]
    total: int
    page: int


class ToggleCharSheetFavoriteResponse(SchemaBase):
    favorited: bool


class UpdateCharSheetInput(SchemaBase):
    name: str = filtered_str()
    description: dict | None = None
    layout: dict


class PublishCharSheetInput(SchemaBase):
    changelog: str | None = filtered_str(default=None)


class GetCharSheetResponse(SchemaBase):
    id: int
    creator: UserData
    forked_from_id: int | None = None
    name: str
    system: SystemData
    description: dict | None
    version_id: int
    version_number: int | None
    is_draft: bool
    layout: dict
    status: CharacterSheet.Status
