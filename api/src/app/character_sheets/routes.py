from fastapi import APIRouter

from app.character_sheets import schemas
from app.database import DBSessionDependency
from app.exceptions import NotFoundException
from app.middleware import Principal
from app.repositories import (
    CharacterSheetRepository,
    SystemRepository,
)

character_sheets = APIRouter(prefix="/character_sheets")


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
