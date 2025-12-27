from typing import Literal, Union

from fastapi import APIRouter, status
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.configs import configs
from app.database import DBSessionDependency
from app.helpers.functions import error_response
from app.middleware import AuthedUser
from app.models.legacy import PM
from app.pms import legacy_schemas as schemas
from app.pms.functions import filter_by_box
from app.repositories.legacy.pm_repository import (
    NoRecipientException,
    PMRepository,
    PMSelfException,
)
from app.schemas import ErrorResponse

pms = APIRouter(prefix="/legacy/pms")


@pms.get(
    "",
    response_model=schemas.PMsListResponse,
)
async def get_pms(
    db_session: DBSessionDependency,
    authed_user: AuthedUser,
    box: Literal["inbox", "outbox"] = "inbox",
    page: int = 1,
):
    if page < 1:
        page = 1

    statement = (
        select(PM)
        .where(filter_by_box(box, authed_user))
        .limit(configs.PAGINATE_PER_PAGE)
        .offset((page - 1) * configs.PAGINATE_PER_PAGE)
        .options(joinedload(PM.recipient), joinedload(PM.sender))
    )

    pms = await db_session.scalars(statement)
    pm_response: list[dict] = []
    for pm in pms:
        model = schemas.PM(
            id=pm.id,
            recipient=schemas.UserDetails(
                id=pm.recipient.id,
                username=pm.recipient.username,
                read=pm.recipient_read,
            ),
            sender=schemas.UserDetails(
                id=pm.sender.id, username=pm.sender.username, read=pm.sender_read
            ),
            title=pm.title,
            message=pm.message,
            reply_to_id=pm.reply_to_id,
        )
        pm_response.append(model.model_dump())

    pm_count = await db_session.scalar(
        select(func.count(PM.id)).where(filter_by_box(box, authed_user))
    )
    return {"pms": pm_response, "count": pm_count or 0, "page": page}


@pms.post(
    "",
    response_model=schemas.NewPMResponse,
    responses={
        400: {
            "model": Union[
                ErrorResponse[schemas.NoRecipientResponse],
                ErrorResponse[schemas.PMSelfResponse],
            ]
        }
    },
)
async def send_pm(
    db_session: DBSessionDependency,
    authed_user: AuthedUser,
    new_pm: schemas.NewPM,
):
    pm_repository = PMRepository(db_session, authed_user=authed_user)
    try:
        pm = await pm_repository.send_pm(
            recipient_username=new_pm.username,
            title=new_pm.title,
            message=new_pm.message,
            reply_to_id=new_pm.reply_to_id,
        )
    except NoRecipientException:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=schemas.NoRecipientResponse().model_dump(),
        )
    except PMSelfException:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=schemas.PMSelfResponse().model_dump(),
        )

    return {"sent": True}
