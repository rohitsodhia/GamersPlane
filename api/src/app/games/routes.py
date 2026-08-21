from fastapi import APIRouter

from app.database import DBSessionDependency
from app.exceptions import NotFoundException
from app.games import schemas
from app.middleware import Auth, Principal
from app.repositories import GameRepository, PlayerRepository, SystemRepository

games = APIRouter(prefix="/games")


@games.post("/", response_model=schemas.NewGameResponse)
async def create_game(
    db_session: DBSessionDependency,
    auth: Auth,
    principal: Principal,
    game_data: schemas.NewGameInput,
):
    system_repository = SystemRepository(db_session)
    system = await system_repository.get_by_id(game_data.system_id)
    if system is None:
        raise NotFoundException("System not found")

    if game_data.allowed_char_sheets:
        char_sheets = await system_repository.get_by_ids(game_data.allowed_char_sheets)
        if len(char_sheets) != len(set(game_data.allowed_char_sheets)):
            raise NotFoundException("One or more allowed char sheets not found")

    game_repository = GameRepository(db_session, principal=principal)
    game = await game_repository.create(
        game_data.title,
        game_data.system_id,
        game_data.allowed_char_sheets,
        principal.id,
        game_data.start,
        game_data.end,
        game_data.post_frequency,
        game_data.num_players,
        game_data.chars_per_player,
        game_data.description,
        game_data.char_gen_info,
        game_data.status,
        game_data.public,
    )

    player_repository = PlayerRepository(db_session, principal=principal)
    await player_repository.attach_player_to_game(game.id, principal.id, is_gm=True)

    return schemas.NewGameResponse(id=game.id)
