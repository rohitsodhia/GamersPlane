from fastapi import APIRouter

from app.character_sheets import schemas
from app.character_sheets.defaults import default_sheet_layout
from app.character_sheets.layout_validation import validate_sheet_layout
from app.database import DBSessionDependency
from app.exceptions import ForbiddenException, NotFoundException
from app.middleware import Principal
from app.models import CharacterSheet
from app.repositories import (
    CharacterSheetRepository,
    SystemRepository,
)

character_sheets = APIRouter(prefix="/character_sheets")


def _char_sheet_response(char_sheet: CharacterSheet) -> schemas.GetCharSheetResponse:
    return schemas.GetCharSheetResponse(
        id=char_sheet.id,
        creator=schemas.UserData(
            id=char_sheet.creator.id,
            username=char_sheet.creator.username,
            avatar=char_sheet.creator.avatar,
        ),
        root_id=char_sheet.root_id,
        name=char_sheet.name,
        system=schemas.SystemData(
            id=char_sheet.system.id,
            name=char_sheet.system.name,
        ),
        layout=char_sheet.layout,
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
        name=data.name, system_id=data.system_id, layout=default_sheet_layout()
    )

    return schemas.CreateCharSheetResponse(id=char_sheet.id)


@character_sheets.get("/my", response_model=schemas.GetMyCharSheetsResponse)
async def get_my_char_sheets(db_session: DBSessionDependency, principal: Principal):
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    created = await char_sheet_repository.get_by_creator_id(principal.id)
    favorited = await char_sheet_repository.get_favorited_by_user_id(principal.id)

    favorited_ids = {char_sheet.id for char_sheet in favorited}
    by_id = {char_sheet.id: char_sheet for char_sheet in (*created, *favorited)}

    ordered = sorted(
        by_id.values(),
        key=lambda char_sheet: (
            char_sheet.id not in favorited_ids,
            char_sheet.name.lower(),
        ),
    )

    return schemas.GetMyCharSheetsResponse(
        char_sheets=[
            schemas.BasicCharSheetData(
                id=char_sheet.id,
                name=char_sheet.name,
                creator=schemas.UserData(
                    id=char_sheet.creator.id,
                    username=char_sheet.creator.username,
                    avatar=char_sheet.creator.avatar,
                ),
                system=schemas.SystemData(
                    id=char_sheet.system.id,
                    name=char_sheet.system.name,
                ),
                favorited=char_sheet.id in favorited_ids,
            )
            for char_sheet in ordered
        ]
    )


@character_sheets.get("/{char_sheet_id}", response_model=schemas.GetCharSheetResponse)
async def get_char_sheet(
    char_sheet_id: int, db_session: DBSessionDependency, principal: Principal
):
    char_sheet_repository = CharacterSheetRepository(db_session, principal=principal)
    char_sheet = await char_sheet_repository.get(char_sheet_id)
    if char_sheet is None:
        raise NotFoundException("Character sheet not found")

    return _char_sheet_response(char_sheet)


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

    char_sheet = await char_sheet_repository.update(char_sheet, layout=data.layout)

    return _char_sheet_response(char_sheet)
