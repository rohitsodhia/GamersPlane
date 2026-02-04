from fastapi import APIRouter

from app.database import DBSessionDependency
from app.middleware import AuthedUser
from app.repositories.legacy.character_repository import CharacterRepository
from app.users import legacy_schemas

users = APIRouter(prefix="/legacy/users")


@users.get("/header", response_model=legacy_schemas.GetHeaderResponse)
async def get_header(db_session: DBSessionDependency, authed_user: AuthedUser):
    character_repository = CharacterRepository(db_session, authed_user)

    characters = await character_repository.get_header_characters()
    ic(characters)
