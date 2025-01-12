from fastapi import APIRouter, Body

from database import DBSessionDependency
from models import System
from systems import schemas

systems = APIRouter(prefix="/systems")


@systems.get("/", response_model=schemas.GetSystemsResponse)
def get_systems(basic: bool = Body(False, embed=True), db_session=DBSessionDependency):
    systems = System.get_all()
    systems_return = []
    for system in systems:
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
            system_dict = system.__dict__
            system_dict.pop("sort_name")
            systems_return.append(system_dict)

    return {"systems": systems_return}
