from typing import Literal

from fastapi import APIRouter
from sqlalchemy import func, select

from app.configs import configs
from app.database import DBSessionDependency
from app.middleware import AuthedUser
from app.models.legacy.pms import PMs
from app.pms import legacy_schemas as schemas
from app.pms.functions import filter_by_box

pms = APIRouter(prefix="/pms")


@pms.get(
    "/",
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
        select(PMs)
        .limit(configs.PAGINATE_PER_PAGE)
        .offset((page - 1) * configs.PAGINATE_PER_PAGE)
    )

    pms = await db_session.scalars(statement)

    pm_count = await db_session.scalar(
        select(func.count(PMs.id)).where(filter_by_box(box, authed_user))
    )
    return {"pms": pms, "count": pm_count or 0, "page": page}
