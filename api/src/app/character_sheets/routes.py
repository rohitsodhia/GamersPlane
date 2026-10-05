from typing import Literal

from fastapi import APIRouter, Query, status

from app.character_sheets import schemas
from app.character_sheets.layout_ids import collect_ids, field_labels
from app.character_sheets.layout_validation import validate_sheet_layout
from app.configs import configs
from app.database import DBSessionDependency
from app.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.middleware import Principal
from app.models import CharacterSheet, CharacterSheetVersion
from app.repositories import (
    CharacterRepository,
    CharacterSheetRepository,
    SystemRepository,
)

character_sheets = APIRouter(prefix="/character_sheets")


def _char_sheet_response(
    char_sheet: CharacterSheet,
    version: CharacterSheetVersion,
    latest_version_number: int | None,
    latest_published: CharacterSheetVersion | None = None,
) -> schemas.GetCharSheetResponse:
    """`latest_published` is only needed when `version` is a draft: the fields
    the draft drops are worked out against it."""
    removed_fields = []
    if version.is_draft and latest_published is not None:
        published_labels = field_labels(latest_published.layout)
        draft_ids = collect_ids(version.layout)
        removed_fields = [
            schemas.RemovedFieldData(id=field_id, label=label)
            for field_id, label in sorted(published_labels.items(), key=lambda f: f[1])
            if field_id not in draft_ids
        ]

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
        latest_version_number=latest_version_number,
        is_draft=version.is_draft,
        changelog=version.changelog,
        layout=version.layout,
        status=char_sheet.status,
        removed_fields=removed_fields,
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
    # For picking a sheet to build a character on, which needs a published
    # version.
    published_only: bool = False,
    # The character picker lists one system's sheets at a time, all at once.
    paginate: bool = True,
):
    if page < 1:
        page = 1

    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheets = await char_sheet_repository.get_all(
        search=search,
        system_id=system_id,
        page=page,
        limit=configs.PAGINATE_PER_PAGE if paginate else None,
        include_favorited=True,
        published_only=published_only,
    )
    total = await char_sheet_repository.count_all(
        search=search,
        system_id=system_id,
        include_favorited=True,
        published_only=published_only,
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


@character_sheets.get(
    "/my/systems", response_model=schemas.GetMyCharSheetSystemsResponse
)
async def get_char_sheet_systems(
    db_session: DBSessionDependency,
    principal: Principal,
    published_only: bool = False,
):
    """The systems the sheets listed by `/my` belong to."""
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    systems = await char_sheet_repository.get_systems(
        include_favorited=True, published_only=published_only
    )

    return schemas.GetMyCharSheetSystemsResponse(
        systems=[
            schemas.SystemData(id=system.id, name=system.name) for system in systems
        ]
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

    latest = await char_sheet_repository.get_latest_published(char_sheet.id)
    response = _char_sheet_response(
        char_sheet,
        sheet_version,
        latest.number if latest is not None else None,
        latest,
    )
    response.favorited = await char_sheet_repository.is_favorited(char_sheet)
    return response


@character_sheets.get(
    "/{char_sheet_id}/versions", response_model=schemas.GetCharSheetVersionsResponse
)
async def get_char_sheet_versions(
    char_sheet_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.get(char_sheet_id)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")

    if not char_sheet.is_public and char_sheet.creator_id != principal.id:
        raise ForbiddenException("Character sheet not available")

    versions = await char_sheet_repository.get_published_versions(char_sheet.id)

    return schemas.GetCharSheetVersionsResponse(
        versions=[
            schemas.PublishedVersionData(
                number=version.number,
                published_at=version.published_at,
                changelog=version.changelog,
            )
            for version in versions
        ]
    )


@character_sheets.post(
    "/{char_sheet_id}/copy", response_model=schemas.CreateCharSheetResponse
)
async def copy_char_sheet(
    char_sheet_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
    version: int | None = None,
):
    """Copy a published version (the latest unless `version` is given) into a
    new draft sheet owned by the caller.

    Anyone who can view the sheet can copy it. So can anyone with a character on
    it, even once it's private or deleted, so they're never stuck on a sheet
    they can't maintain.
    """
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.get(char_sheet_id, include_deleted=True)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")

    can_view = char_sheet.deleted is None and (
        char_sheet.is_public or char_sheet.creator_id == principal.id
    )
    if not can_view:
        character_repository = CharacterRepository(db_session, principal=principal)
        if not await character_repository.has_character_on_sheet(char_sheet.id):
            if char_sheet.deleted is not None:
                raise NotFoundException("Character sheet not found")
            raise ForbiddenException("Character sheet not available")

    if version is None:
        sheet_version = await char_sheet_repository.get_latest_published(char_sheet.id)
        if sheet_version is None:
            raise NotFoundException("Character sheet has no published version")
    else:
        sheet_version = await char_sheet_repository.get_published(
            char_sheet.id, version
        )
        if sheet_version is None:
            raise NotFoundException("Character sheet version not found")

    copied = await char_sheet_repository.create_copy(char_sheet, sheet_version)

    return schemas.CreateCharSheetResponse(id=copied.id)


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
    version = await char_sheet_repository.save_draft(
        char_sheet, layout=data.layout, changelog=data.changelog
    )

    latest = await char_sheet_repository.get_latest_published(char_sheet.id)
    return _char_sheet_response(
        char_sheet,
        version,
        latest.number if latest is not None else None,
        latest,
    )


@character_sheets.post(
    "/{char_sheet_id}/publish", response_model=schemas.PublishCharSheetResponse
)
async def publish_char_sheet(
    char_sheet_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.get(char_sheet_id)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")

    if char_sheet.creator_id != principal.id:
        raise ForbiddenException("Only the creator can publish this character sheet")

    version, id_diff = await char_sheet_repository.publish_draft(char_sheet)

    # Publishing always leaves `version` as the newest published one (a no-op
    # publish returns the latest).
    return schemas.PublishCharSheetResponse(
        **_char_sheet_response(char_sheet, version, version.number).model_dump(),
        added_field_ids=id_diff.added,
        removed_field_ids=id_diff.removed,
    )


@character_sheets.delete(
    "/{char_sheet_id}/draft", response_model=schemas.GetCharSheetResponse
)
async def discard_char_sheet_draft(
    char_sheet_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    """Throw away the unpublished changes. Returns the latest published
    version, which the sheet now shows again."""
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.get(char_sheet_id)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")

    if char_sheet.creator_id != principal.id:
        raise ForbiddenException("Only the creator can discard this sheet's draft")

    version = await char_sheet_repository.discard_draft(char_sheet)

    return _char_sheet_response(char_sheet, version, version.number)


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


@character_sheets.post(
    "/{char_sheet_id}/restore", status_code=status.HTTP_204_NO_CONTENT
)
async def restore_char_sheet(
    char_sheet_id: int, db_session: DBSessionDependency, principal: Principal
):
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.get(char_sheet_id, include_deleted=True)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")
    if char_sheet.creator_id != principal.id:
        # A deleted sheet is hidden from everyone but its creator.
        if char_sheet.deleted is not None:
            raise NotFoundException("Character sheet not found")
        raise ForbiddenException("Only the creator can restore this character sheet")
    if char_sheet.deleted is None:
        raise ConflictException("Character sheet isn't deleted")

    await char_sheet_repository.restore(char_sheet)


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
