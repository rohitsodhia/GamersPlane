from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.database import DBSessionDependency
from app.gamers import legacy_schemas
from app.repositories.legacy import (
    UserRepository,
)
from app.users.functions import get_avatar_path

gamers = APIRouter(prefix="/legacy/gamers")


@gamers.get("", response_model=legacy_schemas.GetGamersResponse)
async def get_gamers(
    db_session: DBSessionDependency,
    get_inactive: bool = False,
):
    user_repository = UserRepository(db_session)
    gamers = await user_repository.get_gamers(get_inactive=get_inactive)
    gamers_return = []
    for gamer in gamers:
        gamers_return.append(
            legacy_schemas.User(
                id=gamer.id,
                username=gamer.username,
                online=gamer.online,
                avatar=get_avatar_path(gamer.id, gamer.avatar_ext),
                lfg=bool(gamer.lfg),
                inactive=(
                    gamer.last_activity.replace(tzinfo=timezone.utc)
                    < datetime.now(timezone.utc) - timedelta(weeks=2)
                ),
            )
        )
    return {"gamers": gamers_return}
