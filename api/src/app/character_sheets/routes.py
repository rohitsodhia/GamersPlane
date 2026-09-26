from typing import Literal

from fastapi import APIRouter, Query, status

from app.character_sheets import schemas
from app.character_sheets.layout_validation import validate_sheet_layout
from app.database import DBSessionDependency
from app.exceptions import ForbiddenException, NotFoundException
from app.middleware import Principal
from app.models import CharacterSheet, CharacterSheetVersion
from app.repositories import (
    CharacterSheetRepository,
    SystemRepository,
)

character_sheets = APIRouter(prefix="/character_sheets")


def _char_sheet_response(
    char_sheet: CharacterSheet, version: CharacterSheetVersion
) -> schemas.GetCharSheetResponse:
    return schemas.GetCharSheetResponse(
        id=char_sheet.id,
        creator=schemas.UserData(
            id=char_sheet.creator.id,
            username=char_sheet.creator.username,
        ),
        forked_from_id=char_sheet.forked_from_id,
        name=char_sheet.name,
        system=schemas.SystemData(
            id=char_sheet.system.id,
            name=char_sheet.system.name,
        ),
        description=char_sheet.description,
        version_id=version.id,
        version_number=version.number,
        is_draft=version.is_draft,
        layout=version.layout,
        status=char_sheet.status,
    )


@character_sheets.post("/", response_model=schemas.CreateCharSheetResponse)
async def create_char_sheet(
    db_session: DBSessionDependency,
    principal: Principal,
    data: schemas.CreateCharSheetInput,
):
    system_repository = SystemRepository(db_session)
    system = await system_repository.get_by_id(data.system_id)
    if system is None:
        raise NotFoundException("System not found")

    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.create(
        name=data.name, system_id=data.system_id
    )

    return schemas.CreateCharSheetResponse(id=char_sheet.id)


@character_sheets.get("/my", response_model=schemas.GetMyCharSheetsResponse)
async def get_char_sheets(
    db_session: DBSessionDependency,
    principal: Principal,
    search: str | None = None,
    system_id: str | None = None,
    page: int = 1,
):
    if page < 1:
        page = 1

    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheets = await char_sheet_repository.get_all(
        search=search, system_id=system_id, page=page, include_favorited=True
    )
    total = await char_sheet_repository.count_all(
        search=search, system_id=system_id, include_favorited=True
    )

    return schemas.GetMyCharSheetsResponse(
        char_sheets=[
            schemas.BasicCharSheetData(
                id=char_sheet.id,
                name=char_sheet.name,
                creator=schemas.UserData(
                    id=char_sheet.creator.id,
                    username=char_sheet.creator.username,
                ),
                system=schemas.SystemData(
                    id=char_sheet.system.id,
                    name=char_sheet.system.name,
                ),
                description=char_sheet.description,
                favorited=favorited,
            )
            for char_sheet, favorited in char_sheets
        ],
        total=total,
        page=page,
    )


@character_sheets.get("/library", response_model=schemas.GetLibraryResponse)
async def get_library(
    db_session: DBSessionDependency,
    principal: Principal,
    search: str | None = None,
    systems: list[str] = Query([]),
    page: int = 1,
):
    if page < 1:
        page = 1

    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheets = await char_sheet_repository.get_library(
        search=search, system_ids=systems, page=page
    )
    total = await char_sheet_repository.count_library(search=search, system_ids=systems)

    return schemas.GetLibraryResponse(
        char_sheets=[
            schemas.LibraryCharSheetData(
                id=char_sheet.id,
                name=char_sheet.name,
                system=schemas.SystemData(
                    id=char_sheet.system.id, name=char_sheet.system.name
                ),
                creator=schemas.LibraryUserData(
                    id=char_sheet.creator.id, username=char_sheet.creator.username
                ),
                description=char_sheet.description,
                status=char_sheet.status,
                favorited=favorited,
            )
            for char_sheet, favorited in char_sheets
        ],
        total=total,
        page=page,
    )


@character_sheets.get("/{char_sheet_id}", response_model=schemas.GetCharSheetResponse)
async def get_char_sheet(
    char_sheet_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
    version: int | Literal["draft"] | None = None,
):
    """`version` pins what's returned: a published version `number`, or
    `"draft"` (creator only). Left out, the caller gets the latest they can see.
    """
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.get(char_sheet_id)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")

    is_creator = char_sheet.creator_id == principal.id
    if not char_sheet.is_public and not is_creator:
        raise ForbiddenException("Character sheet not available")

    if version == "draft":
        if not is_creator:
            raise ForbiddenException("Only the creator can view the draft")
        sheet_version = await char_sheet_repository.get_draft(char_sheet.id)
        if sheet_version is None:
            raise NotFoundException("Character sheet has no draft")
    elif version is not None:
        sheet_version = await char_sheet_repository.get_published(
            char_sheet.id, version
        )
        if sheet_version is None:
            raise NotFoundException("Character sheet version not found")
    else:
        # The creator sees their latest work: a draft, when there is one, is
        # always newer than the latest published version (publishing consumes
        # the draft, and a new draft starts from the latest published layout).
        # Everyone else only ever sees published versions.
        sheet_version = None
        if is_creator:
            sheet_version = await char_sheet_repository.get_draft(char_sheet.id)
        if sheet_version is None:
            sheet_version = await char_sheet_repository.get_latest_published(
                char_sheet.id
            )
        if sheet_version is None:
            raise NotFoundException("Character sheet has no published version")

    return _char_sheet_response(char_sheet, sheet_version)


@character_sheets.patch("/{char_sheet_id}", response_model=schemas.GetCharSheetResponse)
async def update_char_sheet(
    char_sheet_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
    data: schemas.UpdateCharSheetInput,
):
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.get(char_sheet_id)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")

    if char_sheet.creator_id != principal.id:
        raise ForbiddenException("Only the creator can edit this character sheet")

    validate_sheet_layout(data.layout)

    char_sheet = await char_sheet_repository.update_details(
        char_sheet, name=data.name, description=data.description
    )
    version = await char_sheet_repository.save_draft(char_sheet, layout=data.layout)

    return _char_sheet_response(char_sheet, version)


@character_sheets.post(
    "/{char_sheet_id}/publish", response_model=schemas.PublishCharSheetResponse
)
async def publish_char_sheet(
    char_sheet_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
    data: schemas.PublishCharSheetInput,
):
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.get(char_sheet_id)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")

    if char_sheet.creator_id != principal.id:
        raise ForbiddenException("Only the creator can publish this character sheet")

    version, id_diff = await char_sheet_repository.publish_draft(
        char_sheet, changelog=data.changelog
    )

    return schemas.PublishCharSheetResponse(
        **_char_sheet_response(char_sheet, version).model_dump(),
        added_field_ids=id_diff.added,
        removed_field_ids=id_diff.removed,
    )


@character_sheets.delete("/{char_sheet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_char_sheet(
    char_sheet_id: int, db_session: DBSessionDependency, principal: Principal
):
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.get(char_sheet_id)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")
    if char_sheet.creator_id != principal.id:
        raise ForbiddenException("Only the creator can delete this character sheet")

    await char_sheet_repository.delete(char_sheet)


@character_sheets.patch(
    "/{char_sheet_id}/toggle_favorite",
    response_model=schemas.ToggleCharSheetFavoriteResponse,
)
async def toggle_char_sheet_favorite(
    char_sheet_id: int, db_session: DBSessionDependency, principal: Principal
):
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.get(char_sheet_id)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")
    if not char_sheet.is_public and char_sheet.creator_id != principal.id:
        raise ForbiddenException("Character sheet not available")

    favorited = await char_sheet_repository.toggle_favorite(char_sheet)

    return schemas.ToggleCharSheetFavoriteResponse(favorited=favorited)
