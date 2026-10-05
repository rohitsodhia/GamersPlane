from __future__ import annotations

from datetime import datetime

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


class GetMyCharSheetSystemsResponse(SchemaBase):
    systems: list[SystemData]


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
    # Saved on the draft; ignored when the save doesn't start or update one.
    changelog: dict | None = None


class RemovedFieldData(SchemaBase):
    id: str
    # The field's value path in the published layout, e.g. `abilities.str`.
    label: str


class GetCharSheetResponse(SchemaBase):
    id: int
    creator: UserData
    forked_from_id: int | None = None
    name: str
    system: SystemData
    description: dict | None
    version_id: int
    version_number: int | None
    # The sheet's newest published number, whichever version is returned;
    # `None` until the first publish. A draft will publish as this + 1.
    latest_version_number: int | None
    is_draft: bool
    changelog: dict | None
    layout: dict
    status: CharacterSheet.Status
    # Only set on a draft: fields in the latest published version that the
    # draft no longer has, so the author can be warned before publishing.
    removed_fields: list[RemovedFieldData] = []
    # Only filled by the GET; the creator-only write routes leave it out.
    favorited: bool | None = None


class PublishedVersionData(SchemaBase):
    number: int
    published_at: datetime
    changelog: dict | None


class GetCharSheetVersionsResponse(SchemaBase):
    # Published versions only, newest first; drafts have no history yet.
    versions: list[PublishedVersionData]


class PublishCharSheetResponse(GetCharSheetResponse):
    # Field ids (see `layout_ids.py`) new to this version / missing from it,
    # relative to the previously published version -- lets the publish UI show
    # the author what changed before they confirm.
    added_field_ids: list[str]
    removed_field_ids: list[str]
