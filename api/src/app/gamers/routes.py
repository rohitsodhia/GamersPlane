from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.database import DBSessionDependency
from app.gamers import schemas
from app.models import UserMeta
from app.repositories.user_repository import (
    GAMERS_PER_PAGE,
    GamerSort,
    UserRepository,
)

gamers = APIRouter(prefix="/gamers")

ONLINE_WITHIN = timedelta(minutes=15)


@gamers.get("", response_model=schemas.GetGamersResponse)
async def get_gamers(
    db_session: DBSessionDependency,
    search: str | None = None,
    lfg: bool = False,
    include_inactive: bool = False,
    sort: GamerSort = "name",
    page: int = 1,
):
    if page < 1:
        page = 1

    user_repository = UserRepository(db_session)
    found = await user_repository.get_gamers(
        search=search,
        lfg=lfg,
        include_inactive=include_inactive,
        sort=sort,
        page=page,
        limit=GAMERS_PER_PAGE,
    )
    total = await user_repository.count_gamers(
        search=search, lfg=lfg, include_inactive=include_inactive
    )

    online_cutoff = datetime.now(timezone.utc) - ONLINE_WITHIN
    return {
        "gamers": [
            {
                "id": user.id,
                "username": user.username,
                "avatar": user.avatar_url,
                "online": user.last_activity is not None
                and user.last_activity >= online_cutoff,
                "lfg": any(
                    meta.key == UserMeta.MetaKeys.LOOKING_FOR_A_GAME.value
                    and meta.value
                    for meta in user.meta
                ),
                "lastActivity": user.last_activity,
            }
            for user in found
        ],
        "total": total,
    }
