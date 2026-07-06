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
    custom_dict = {}
    for system in await system_repository.get():
        system_dict = {}
        if basic:
            system_dict = {
                "id": system.id,
                "name": system.name,
                "genres": [genre.genre for genre in system.genres],
                "has_char_sheet": system.has_char_sheet,
            }
        else:
            system_dict = {
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

        if system.id == "custom":
            custom_dict = system_dict
            continue
        systems_return.append(system_dict)
    systems_return = [custom_dict] + systems_return

    return {"systems": systems_return}
