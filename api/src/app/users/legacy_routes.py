from fastapi import APIRouter

from app.database import DBSessionDependency
from app.middleware import AuthedUser
from app.repositories.legacy import (
    CharacterRepository,
    GameRepository,
    PMRepository,
    UserRepository,
)
from app.users import legacy_schemas

users = APIRouter(prefix="/legacy/users")


@users.get("/header", response_model=legacy_schemas.GetHeaderResponse)
async def get_header(db_session: DBSessionDependency, authed_user: AuthedUser):
    character_repository = CharacterRepository(db_session, authed_user)
    game_repository = GameRepository(db_session, authed_user)
    user_repository = UserRepository(db_session)
    pm_repository = PMRepository(db_session, authed_user)

    characters = await character_repository.get_header_characters()
    if len(characters) > 0 and characters[0]["isFavorite"]:
        characters = filter(lambda x: x["isFavorite"], characters)
    elif len(characters) > 0:
        characters = characters[:6]

    games = await game_repository.get_header_games()
    if len(games) > 0 and games[0]["isFavorite"]:
        games = filter(lambda x: x["isFavorite"], games)
    elif len(games) > 0:
        games = filter(lambda x: not x["retired"], games[:6])

    return {
        "characters": characters,
        "games": games,
        "avatar": await user_repository.get_avatar(authed_user.id),
        "pmCount": await pm_repository.count_pms(authed_user.id, state="unread"),
    }
