from fastapi import APIRouter

from app.database import DBSessionDependency
from app.helpers.decorators import public
from app.repositories import SystemRepository
from app.systems import schemas

systems = APIRouter(prefix="/systems")


@systems.get("/", response_model=schemas.GetSystemsResponse)
@public
async def get_systems(db_session: DBSessionDependency, basic: bool = False):
    system_repository = SystemRepository(db_session)
    systems_return = []
    for system in await system_repository.get():
        if basic:
            systems_return.append(
                {
                    "id": system.id,
                    "name": system.name,
                    "genres": [genre.genre for genre in system.genres],
                    "has_char_sheet": system.has_char_sheet,
                }
            )
        else:
            systems_return.append(
                {
                    "id": system.id,
                    "name": system.name,
                    "sort_name": system.sort_name,
                    "publisher": {
                        "name": system.publisher.name,
                        "website": system.publisher.website,
                    }
                    if system.publisher
                    else None,
                    "genres": [genre.genre for genre in system.genres],
                    "basics": system.basics,
                    "has_char_sheet": system.has_char_sheet,
                    "enabled": system.enabled,
                }
            )

    return {"systems": systems_return}
