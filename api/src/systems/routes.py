from fastapi import APIRouter, Body

from systems import schemas
from systems.models import System

systems = APIRouter(prefix="/systems")


@systems.get("/", response_model=schemas.GetSystemsResponse)
def get_systems(basic: bool = Body(False, embed=True)):
    systems = System.objects
    if basic:
        systems = systems.basic()
    systems = systems.order_by("sortName").values()

    return {"systems": [system for system in systems]}
