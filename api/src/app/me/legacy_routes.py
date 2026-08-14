from fastapi import APIRouter

from app.database import LegacyDBSessionDependency
from app.me import legacy_schemas
from app.middleware import Principal
from app.repositories.legacy import (
    CharacterRepository,
    GameRepository,
    PMRepository,
    UserRepository,
)

me = APIRouter(prefix="/legacy/me")


@me.get("/header", response_model=legacy_schemas.GetHeaderResponse)
async def get_header(db_session: LegacyDBSessionDependency, principal: Principal):
    character_repository = CharacterRepository(db_session, principal)
    game_repository = GameRepository(db_session, principal)
    user_repository = UserRepository(db_session)
    pm_repository = PMRepository(db_session, principal)

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
        "avatar": await user_repository.get_avatar(principal.id),
        "pmCount": await pm_repository.count_pms(principal.id, state="unread"),
    }
