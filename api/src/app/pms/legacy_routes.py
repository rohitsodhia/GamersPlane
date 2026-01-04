from typing import Literal, Union

from fastapi import APIRouter, status

from app.configs import configs
from app.database import DBSessionDependency
from app.exceptions import ForbiddenException, NotFoundException
from app.helpers.functions import error_response
from app.middleware import AuthedUser
from app.pms import legacy_schemas as schemas
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
    limit: int = configs.PAGINATE_PER_PAGE,
):
    if page < 1:
        page = 1

    pm_repository = PMRepository(db_session, authed_user=authed_user)

    pms = await pm_repository.get_pms(
        user_id=authed_user.id,
        box=box,
        page=page,
        limit=limit,
    )
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
            datestamp=str(pm.datestamp),
            reply_to_id=pm.reply_to_id,
        )
        pm_response.append(model.model_dump())

    pm_count = await pm_repository.count_pms(user_id=authed_user.id, box=box)

    return {"pms": pm_response, "count": pm_count or 0, "page": page}


@pms.get("/{id}", response_model=schemas.GetPMResponse)
async def get_pm(
    db_session: DBSessionDependency,
    authed_user: AuthedUser,
    id: int,
    includeSelfHistory: bool = False,
):
    pm_repository = PMRepository(db_session, authed_user=authed_user)

    try:
        pm = await pm_repository.get_pm(id)
    except NotFoundException:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"Not found": True},
        )
    except ForbiddenException:
        return error_response(
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if authed_user.id == pm.recipient.id:
        pm.recipient_read = True
    elif authed_user.id == pm.sender.id:
        pm.sender_read = True
    await db_session.commit()

    model = schemas.PMWithHistory(
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
        datestamp=str(pm.datestamp),
        reply_to_id=pm.reply_to_id,
    )

    history = []

    for pm in await pm_repository.get_pm_history(pm):
        history.append(
            schemas.PM(
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
                datestamp=str(pm.datestamp),
                reply_to_id=pm.reply_to_id,
            )
        )

    if includeSelfHistory:
        history.insert(
            0,
            schemas.PM(**model.model_dump()),
        )

    model.history = history

    return {"pm": model.model_dump()}


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
