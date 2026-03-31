from fastapi import APIRouter

from app.database import DBSessionDependency
from app.gamers import legacy_schemas
from app.repositories.legacy import (
    UserRepository,
)

gamers = APIRouter(prefix="/legacy/gamers")


@gamers.get("", response_model=legacy_schemas.GetGamersResponse)
async def get_gamers(db_session: DBSessionDependency, showInactive: bool = False):
    user_repository = UserRepository(db_session)
    gamers = user_repository.get_gamers(showInactive)
    return {"gamers": gamers}
