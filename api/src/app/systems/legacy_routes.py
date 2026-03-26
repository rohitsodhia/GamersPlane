from fastapi import APIRouter

from app.database import DBSessionDependency
from app.repositories.legacy.system_repository import SystemRepository
from app.systems import legacy_schemas as schemas

systems = APIRouter(prefix="/legacy/systems")


@systems.get("", response_model=schemas.GetSystemsResponse)
async def get_systems(db_session: DBSessionDependency):
    system_repository = SystemRepository(db_session)
    systems = await system_repository.get_systems()
    systems_return = []
    for system in systems:
        system_dict = dict(system.__dict__)
        if "site" in system_dict.get("publisher", {}):
            system_dict["publisher"]["website"] = system_dict["publisher"]["site"]
            del system_dict["publisher"]["site"]
        systems_return.append(system_dict)

    return {"systems": systems_return}
