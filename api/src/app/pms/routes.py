from fastapi import APIRouter, status

from app.auth import schemas
from app.database import DBSessionDependency
from app.helpers.decorators import public
from app.helpers.functions import error_response
from app.schemas import ErrorResponse

pms = APIRouter(prefix="/pms")


@pms.get(
    "/",
    response_model=schemas,
    responses={404: {"model": ErrorResponse[schemas]}},
)
@public
async def get_pms(user_details: schemas.UserInput, db_session: DBSessionDependency):
    return error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"invalid_user": True},
    )
