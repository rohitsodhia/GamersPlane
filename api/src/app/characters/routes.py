from fastapi import APIRouter

from app.characters import schemas
from app.database import DBSessionDependency
from app.exceptions import ForbiddenException, NotFoundException
from app.middleware import Principal
from app.repositories import CharacterRepository, CharacterSheetRepository

characters = APIRouter(prefix="/characters")


@characters.post("/", response_model=schemas.CreateCharacterResponse)
async def create_character(
    db_session: DBSessionDependency,
    principal: Principal,
    data: schemas.CreateCharacterInput,
):
    sheet_repository = CharacterSheetRepository(db_session, principal)
    sheet = await sheet_repository.get(data.character_sheet_id)
    if sheet is None:
        raise NotFoundException("Character sheet not found")
    if not sheet.is_public and sheet.creator_id != principal.id:
        raise ForbiddenException("Character sheet not available")

    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.create(
        character_sheet_id=data.character_sheet_id,
        label=data.label,
        type=data.type,
    )

    return schemas.CreateCharacterResponse(id=character.id)


@characters.get("/{character_id}", response_model=schemas.GetCharacterResponse)
async def get_character(
    character_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    character_repository = CharacterRepository(db_session, principal)
    character = await character_repository.get(character_id)
    if character is None:
        raise NotFoundException("Character not found")

    sheet = character.character_sheet

    return schemas.GetCharacterResponse(
        id=character.id,
        label=character.label,
        name=character.name,
        type=character.type,
        values=character.values,
        character_sheet=schemas.CharacterSheetData(
            id=sheet.id,
            name=sheet.name,
            creator=schemas.UserData(
                id=sheet.creator.id,
                username=sheet.creator.username,
                avatar=sheet.creator.avatar,
            ),
            system=schemas.SystemData(
                id=sheet.system.id,
                name=sheet.system.name,
            ),
            layout=sheet.layout,
        ),
    )
