from fastapi import APIRouter

from app.database import DBSessionDependency
from app.exceptions import NotFoundException
from app.games import schemas
from app.helpers.decorators import public
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
        game_data.post_frequency,
        game_data.num_players,
        game_data.chars_per_player,
        game_data.description,
        game_data.char_gen_info,
        game_data.public,
        game_data.recruitment_thread_id,
        game_data.advanced_options,
    )

    player_repository = PlayerRepository(db_session, principal=principal)
    await player_repository.attach_player_to_game(game.id, principal.id, is_gm=True)

    return schemas.NewGameResponse(id=game.id)


@games.get("/{game_id}", response_model=schemas.GetGameResponse)
@public
async def get_game(
    game_id: int, db_session: DBSessionDependency, auth: Auth, principal: Principal
):
    game_repository = GameRepository(db_session, principal=principal)
    game = await game_repository.get(game_id)
    if game is None:
        raise NotFoundException("Game not found")

    is_gm = principal is not None and principal.id == game.gm_id

    player_repository = PlayerRepository(db_session, principal=principal)
    players = await player_repository.get_players_for_game(
        game_id, only_accepted=not is_gm
    )

    return schemas.GetGameResponse(
        id=game.id,
        title=game.title,
        system=game.system_id,
        allowed_char_sheets=[system.id for system in game.allowed_char_sheets],
        gm=schemas.UserData(id=game.gm.id, username=game.gm.username),
        created=game.created,
        end=game.end,
        post_frequency=schemas.PostFrequencyData(
            times_per=game.post_frequency.times_per,
            per_period=game.post_frequency.per_period,
        ),
        num_players=game.num_players,
        chars_per_player=game.chars_per_player,
        description=game.description,
        char_gen_info=game.char_gen_info,
        root_forum_id=game.root_forum_id,
        status=game.status.name.lower(),
        public=game.public,
        recruitment_thread_id=game.recruitment_thread_id,
        advanced_options=game.advanced_options,
        retired=game.retired,
        players=schemas.PlayersData(
            players=[
                schemas.PlayerData(
                    id=player.user.id,
                    username=player.user.username,
                    is_gm=player.is_gm,
                    state=player.state.value,
                )
                for player in players
            ]
        ),
    )
