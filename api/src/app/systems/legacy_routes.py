from fastapi import APIRouter

from app.database import DBSessionDependency
from app.helpers.decorators import public
from app.models.legacy import System
from app.repositories.legacy.system_repository import SystemRepository
from app.systems import legacy_schemas as schemas

systems = APIRouter(prefix="/legacy/systems")


@public
@systems.get("", response_model=schemas.GetSystemsResponse)
async def get_systems(db_session: DBSessionDependency):
    system_repository = SystemRepository(db_session)
    systems = await system_repository.get_systems()
    systems_return = []
    custom_details = System()
    for system in systems:
        system_dict = dict(system.__dict__)
        if "site" in system_dict.get("publisher", {}):
            system_dict["publisher"]["website"] = system_dict["publisher"]["site"]
            del system_dict["publisher"]["site"]
        if system.id == "custom":
            custom_details = system
            continue
        systems_return.append(system_dict)

    systems_return = [custom_details] + systems_return
    return {"systems": systems_return, "num_systems": len(systems_return)}
