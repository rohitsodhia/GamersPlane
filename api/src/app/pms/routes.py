from fastapi import APIRouter, status

from app.auth import schemas
from app.database import DBSessionDependency
from app.helpers.decorators import public
from app.helpers.functions import error_response

pms = APIRouter(prefix="/pms")


@pms.get(
    "/",
    response_model=schemas,
)
@public
async def get_pms(user_details: schemas.UserInput, db_session: DBSessionDependency):
    pass
