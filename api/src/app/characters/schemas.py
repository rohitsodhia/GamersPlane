from __future__ import annotations

import json

from pydantic import field_validator

from app.models import Character
from app.schema_base import SchemaBase, filtered_str

# Serialized size cap on a character's `values` document, measured as the
# `json.dumps` length (non-ASCII is escaped, so this over- rather than
# under-counts the stored bytes).
MAX_VALUES_SIZE = 512 * 1024


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
    label: str | None = filtered_str(default=None)
    type: Character.Type | None = None
    values: dict | None = None

    @field_validator("values")
    @classmethod
    def validate_values_size(cls, v: dict | None) -> dict | None:
        # Keys are checked against the sheet on save (`character_values.py`),
        # but values themselves aren't, so keep a client from storing an
        # unbounded blob.
        if v is not None and len(json.dumps(v)) > MAX_VALUES_SIZE:
            raise ValueError(
                f"Character values can't exceed {MAX_VALUES_SIZE // 1024} KB"
            )
        return v


class CharacterSheetData(SchemaBase):
    id: int
    name: str
    creator: UserData
    system: SystemData


class CharacterAvatarData(SchemaBase):
    id: int
    url: str
    is_primary: bool


class GetCharacterResponse(SchemaBase):
    id: int
    user_id: int
    label: str
    name: str | None = None
    type: Character.Type
    values: dict | None = None
    in_library: bool
    character_sheet_id: int
    # None once the sheet has been deleted; the character keeps working from
    # its pinned version's layout.
    character_sheet: CharacterSheetData | None
    sheet_deleted: bool
    # The sheet version this character is pinned to, and its layout.
    version_id: int
    version_number: int
    layout: dict
    avatars: list[CharacterAvatarData]


class LibraryUserData(SchemaBase):
    id: int
    username: str


class CharacterListSheetData(SchemaBase):
    id: int
    name: str
    system: SystemData


class CharacterListItem(SchemaBase):
    id: int
    label: str
    type: Character.Type
    in_library: bool
    user: LibraryUserData
    character_sheet_id: int
    character_sheet: CharacterListSheetData | None
    sheet_deleted: bool


class GetCharactersResponse(SchemaBase):
    characters: list[CharacterListItem]
    total: int
    page: int


class LibraryCharacterData(SchemaBase):
    id: int
    label: str
    system: SystemData
    user: LibraryUserData
    favorited: bool


class GetLibraryResponse(SchemaBase):
    characters: list[LibraryCharacterData]
    total: int
    page: int


class ToggleCharacterFavoriteResponse(SchemaBase):
    favorited: bool


class UpdateCharacterAvatarResponse(SchemaBase):
    success: bool = True
    avatar: CharacterAvatarData


class DeleteCharacterAvatarResponse(SchemaBase):
    success: bool = True


class SetPrimaryCharacterAvatarResponse(SchemaBase):
    success: bool = True
    avatar: CharacterAvatarData
