from typing import Literal

from fastapi import APIRouter, status

from app.database import DBSessionDependency
from app.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.games import schemas
from app.helpers.decorators import public
from app.middleware import Auth, Principal
from app.models import Game, Player
from app.repositories import (
    FavoritesRepository,
    GameRepository,
    PlayerRepository,
    SystemRepository,
    UserRepository,
)
from app.repositories.player_repository import DuplicatePlayerError

games = APIRouter(prefix="/games")


@games.post("/", response_model=schemas.GameIdResponse)
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
    await player_repository.attach_player_to_game(
        game.id, principal.id, is_gm=True, state=Player.States.ACCEPTED
    )

    return schemas.GameIdResponse(id=game.id)


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
    all_players = await player_repository.get_players_for_game(
        game_id, only_accepted=not is_gm
    )

    players = [
        schemas.PlayerData(
            id=player.user.id,
            username=player.user.username,
            is_gm=player.is_gm,
            state=player.state.value,
        )
        for player in all_players
    ]

    viewer_state = None
    if principal is not None:
        viewer_player = await player_repository.get_player(game_id, principal.id)
        if viewer_player is not None:
            viewer_state = viewer_player.state.value

    favorited = False
    if principal is not None:
        favorites_repository = FavoritesRepository(db_session, principal)
        favorited = await favorites_repository.get_game_favorite_status(game_id)

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
        players=players,
        viewer_state=viewer_state,
        favorited=favorited,
    )


@games.patch("/{game_id}", response_model=schemas.GameIdResponse)
async def update_game(
    game_id: int,
    request_body: schemas.UpdateGameInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    game = await game_repository.get(game_id)
    if not game:
        raise NotFoundException("Game not found")

    if principal.id != game.gm_id:
        raise ForbiddenException("Only game masters can edit games")

    system_repository = SystemRepository(db_session)
    system = await system_repository.get_by_id(request_body.system_id)
    if system is None:
        raise NotFoundException("System not found")

    update_data = request_body.model_dump()
    if request_body.allowed_char_sheets:
        char_sheets = await system_repository.get_by_ids(
            request_body.allowed_char_sheets
        )
        if len(char_sheets) != len(set(request_body.allowed_char_sheets)):
            raise NotFoundException("One or more allowed char sheets not found")
        update_data["allowed_char_sheets"] = list(char_sheets)
    else:
        update_data["allowed_char_sheets"] = []

    return await game_repository.update(game, **update_data)


@games.patch("/{game_id}/toggle/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def toggle_game_flag(
    game_id: int,
    key: Literal["status", "public"],
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    game = await game_repository.get(game_id)
    if not game:
        raise NotFoundException("Game not found")

    if key == "status":
        new_value = (
            Game.Statuses.CLOSED
            if game.status is Game.Statuses.OPEN
            else Game.Statuses.OPEN
        )
    else:
        new_value = not game.public

    await game_repository.update(game, **{key: new_value})


@games.post("/{game_id}/favorite", response_model=schemas.FavoriteGameResponse)
async def favorite_game(
    game_id: int, db_session: DBSessionDependency, principal: Principal
):
    game_repository = GameRepository(db_session, principal=principal)
    if not await game_repository.exists(game_id):
        raise NotFoundException("Game not found")

    favorites_repository = FavoritesRepository(db_session, principal)
    is_favorite = await favorites_repository.toggle_game_favorite(game_id)

    return schemas.FavoriteGameResponse(favorite=is_favorite)


@games.post("/{game_id}/invite", status_code=status.HTTP_204_NO_CONTENT)
async def invite_player(
    game_id: int,
    request_body: schemas.InvitePlayerInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    if not await game_repository.exists(game_id):
        raise NotFoundException("Game not found")

    player_repository = PlayerRepository(db_session, principal=principal)
    if not await player_repository.is_gm(game_id, principal.id):
        raise ForbiddenException("Only game masters can invite players")

    username = request_body.username
    user_repository = UserRepository(db_session)
    user = await user_repository.get_user_by_username(username)
    if user is None:
        raise NotFoundException("User not found")

    try:
        await player_repository.attach_player_to_game(
            game_id, user.id, state=Player.States.INVITED
        )
    except DuplicatePlayerError as e:
        raise ConflictException("Player already invited to game") from e


@games.post("/{game_id}/apply", status_code=status.HTTP_204_NO_CONTENT)
async def apply_to_game(
    game_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    game = await game_repository.get(game_id)
    if not game:
        raise NotFoundException("Game not found")
    if game.status is Game.Statuses.CLOSED or not game.public:
        raise ForbiddenException("Game is not accepting applications")

    player_repository = PlayerRepository(db_session, principal=principal)

    try:
        await player_repository.attach_player_to_game(
            game_id, principal.id, state=Player.States.APPLIED
        )
    except DuplicatePlayerError as e:
        raise ConflictException("Player already in game") from e


@games.post(
    "/{game_id}/player/{user_id}/approve", status_code=status.HTTP_204_NO_CONTENT
)
async def approve_player(
    game_id: int,
    user_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    game = await game_repository.get(game_id)
    if not game:
        raise NotFoundException("Game not found")

    player_repository = PlayerRepository(db_session, principal=principal)
    if not await player_repository.is_gm(game_id, principal.id):
        raise ForbiddenException("Only game masters can approve players")

    player = await player_repository.get_player(game_id, user_id)
    if player is None:
        raise NotFoundException("Player not in game")
    if player.state is Player.States.ACCEPTED:
        raise ConflictException("Player already accepted")

    await player_repository.update_state(player, state=Player.States.ACCEPTED)


@games.post(
    "/{game_id}/player/{user_id}/toggle_gm", status_code=status.HTTP_204_NO_CONTENT
)
async def toggle_gm(
    game_id: int,
    user_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    game = await game_repository.get(game_id)
    if not game:
        raise NotFoundException("Game not found")

    player_repository = PlayerRepository(db_session, principal=principal)
    if not await player_repository.is_gm(game_id, principal.id):
        raise ForbiddenException("Only game masters can toggle GM status")

    if user_id == game.gm_id:
        raise ForbiddenException("Primary GM cannot be demoted")

    player = await player_repository.get_player(game_id, user_id)
    if player is None:
        raise NotFoundException("Player not in game")

    await player_repository.update_state(player, is_gm=not player.is_gm)


@games.delete("/{game_id}/player/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_player(
    game_id: int,
    user_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    game = await game_repository.get(game_id)
    if not game:
        raise NotFoundException("Game not found")

    player_repository = PlayerRepository(db_session, principal=principal)
    player = await player_repository.get_player(game_id, user_id)
    if player is None:
        raise NotFoundException("Player not in game")

    if user_id == game.gm_id:
        raise ForbiddenException("Primary GM cannot be removed from game")
    if (
        not await player_repository.is_gm(game_id, principal.id)
        and principal.id != user_id
    ):
        raise ForbiddenException("Only game masters can edit players")

    await player_repository.delete_player(player)
