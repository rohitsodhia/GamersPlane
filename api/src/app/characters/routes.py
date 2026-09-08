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
