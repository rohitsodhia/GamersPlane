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
    label: str | None = filtered_str(default=None)
    type: Character.Type | None = None
    values: dict | None = None


class CharacterSheetData(SchemaBase):
    id: int
    name: str
    creator: UserData
    system: SystemData
    layout: dict


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
    character_sheet: CharacterSheetData
    avatars: list[CharacterAvatarData]


class LibraryUserData(SchemaBase):
    id: int
    username: str


class CharacterListItem(GetCharacterResponse):
    user: LibraryUserData


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
