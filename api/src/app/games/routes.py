from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Query, UploadFile, status

from app.configs import configs
from app.database import DBSessionDependency
from app.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationError,
)
from app.games import npc_schemas, schemas
from app.games.functions import (
    get_deck_or_404,
    get_game_or_404,
    get_npc_or_404,
    get_player_or_404,
    require_game_exists,
    require_game_image,
    require_gm,
    require_not_retired,
)
from app.games.npcs import build_image_data, build_npc_data
from app.helpers.avatars import process_avatar_upload, save_avatar
from app.helpers.decorators import public
from app.helpers.remote_image import fetch_remote_image
from app.middleware import Principal
from app.models import Character, Deck, Game, Player
from app.repositories import (
    CharacterRepository,
    DeckRepository,
    FavoritesRepository,
    GameNPCRepository,
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
    principal: Principal,
    game_data: schemas.NewGameInput,
):
    system_repository = SystemRepository(db_session)
    system = await system_repository.get_by_id(game_data.system_id)
    if system is None:
        raise NotFoundException("System not found")

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


def _game_to_data(
    game: Game, player_counts: dict[int, int], favorited_ids: set[int]
) -> schemas.GameData:
    return schemas.GameData(
        id=game.id,
        title=game.title,
        system=game.system.name,
        gm=schemas.UserData(id=game.gm.id, username=game.gm.username),
        post_frequency=schemas.PostFrequencyData(
            times_per=game.post_frequency.times_per,
            per_period=game.post_frequency.per_period,
        ),
        num_players=game.num_players,
        player_count=player_counts.get(game.id, 0),
        forum_id=game.root_forum_id,
        is_retired=game.retired is not None,
        status=game.status.name.lower(),
        public=game.public,
        favorited=game.id in favorited_ids,
    )


async def _get_player_counts_and_favorites(
    db_session: DBSessionDependency,
    game_repository: GameRepository,
    principal: Principal,
    game_ids: list[int],
) -> tuple[dict[int, int], set[int]]:
    player_counts = await game_repository.get_player_counts(game_ids)

    favorited_ids: set[int] = set()
    if principal is not None:
        favorites_repository = FavoritesRepository(db_session, principal)
        favorited_ids = await favorites_repository.get_favorited_game_ids(game_ids)

    return player_counts, favorited_ids


@games.get("/", response_model=schemas.GetGamesResponse)
@public
async def get_games(
    db_session: DBSessionDependency,
    principal: Principal,
    search: str | None = None,
    systems: list[str] = Query([]),
    page: int = 1,
):
    if page < 1:
        page = 1

    game_repository = GameRepository(db_session, principal=principal)
    games = await game_repository.get_browse(
        search=search, system_ids=systems, page=page
    )
    count = await game_repository.count_browse(search=search, system_ids=systems)

    game_ids = [game.id for game in games]
    player_counts, favorited_ids = await _get_player_counts_and_favorites(
        db_session, game_repository, principal, game_ids
    )

    return schemas.GetGamesResponse(
        games=[_game_to_data(game, player_counts, favorited_ids) for game in games],
        count=count,
        page=page,
    )


@games.get("/my", response_model=schemas.GetMyGamesResponse)
async def get_my_games(db_session: DBSessionDependency, principal: Principal):
    game_repository = GameRepository(db_session, principal=principal)
    games = await game_repository.get_player_games(principal.id)

    game_ids = [game.id for game in games]
    player_counts, favorited_ids = await _get_player_counts_and_favorites(
        db_session, game_repository, principal, game_ids
    )
    gm_game_ids = await game_repository.get_principal_gm_game_ids(game_ids)

    return schemas.GetMyGamesResponse(
        games=[
            schemas.MyGameData(
                **_game_to_data(game, player_counts, favorited_ids).model_dump(),
                is_gm=game.id in gm_game_ids,
            )
            for game in games
        ],
    )


LATEST_GAMES_LIMIT = 3


@games.get("/latest", response_model=schemas.GetLatestGamesResponse)
@public
async def get_latest_games(
    db_session: DBSessionDependency, principal: Principal, system: str | None = None
):
    game_repository = GameRepository(db_session, principal=principal)
    games = await game_repository.get_latest(system, LATEST_GAMES_LIMIT)

    game_ids = [game.id for game in games]
    player_counts, favorited_ids = await _get_player_counts_and_favorites(
        db_session, game_repository, principal, game_ids
    )

    return schemas.GetLatestGamesResponse(
        games=[_game_to_data(game, player_counts, favorited_ids) for game in games],
    )


@games.get("/{game_id}", response_model=schemas.GetGameResponse)
@public
async def get_game(game_id: int, db_session: DBSessionDependency, principal: Principal):
    game_repository = GameRepository(db_session, principal=principal)
    game = await get_game_or_404(game_repository, game_id)

    is_gm = principal is not None and principal.id == game.gm_id

    player_repository = PlayerRepository(db_session, principal=principal)
    all_players = await player_repository.get_players_for_game(
        game_id, only_accepted=not is_gm
    )

    viewer_player = None
    viewer_state = None
    if principal is not None:
        viewer_player = await player_repository.get_player(game_id, principal.id)
        if viewer_player is not None:
            viewer_state = viewer_player.state.value
    viewer_is_gm = viewer_player is not None and viewer_player.is_gm

    # Pending submissions are only shown to the GMs and the character's owner.
    character_repository = CharacterRepository(db_session, principal=principal)
    characters_by_user: dict[int, list[schemas.PlayerCharacterData]] = {}
    for character in await character_repository.get_in_game(game_id):
        if not (
            character.approved
            or viewer_is_gm
            or (principal is not None and character.user_id == principal.id)
        ):
            continue
        characters_by_user.setdefault(character.user_id, []).append(
            schemas.PlayerCharacterData(
                id=character.id,
                label=character.label,
                type=character.type,
                approved=character.approved,
            )
        )

    players = [
        schemas.PlayerData(
            id=player.user.id,
            username=player.user.username,
            is_gm=player.is_gm,
            state=player.state.value,
            characters=characters_by_user.get(player.user.id, []),
        )
        for player in all_players
    ]

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
    game = await get_game_or_404(game_repository, game_id)

    if principal.id != game.gm_id:
        raise ForbiddenException("Only game masters can edit games")

    system_repository = SystemRepository(db_session)
    system = await system_repository.get_by_id(request_body.system_id)
    if system is None:
        raise NotFoundException("System not found")

    update_data = request_body.model_dump()
    char_sheets = await system_repository.get_by_ids(request_body.allowed_char_sheets)
    if len(char_sheets) != len(set(request_body.allowed_char_sheets)):
        raise NotFoundException("One or more allowed char sheets not found")
    update_data["allowed_char_sheets"] = list(char_sheets)

    return await game_repository.update(game, **update_data)


@games.patch("/{game_id}/toggle/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def toggle_game_flag(
    game_id: int,
    key: Literal["status", "public"],
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    game = await get_game_or_404(game_repository, game_id)

    if principal.id != game.gm_id:
        raise ForbiddenException("Only game masters can edit games")

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
    await require_game_exists(game_repository, game_id)

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
    await require_game_exists(game_repository, game_id)

    player_repository = PlayerRepository(db_session, principal=principal)
    await require_gm(
        player_repository, game_id, principal.id, "Only game masters can invite players"
    )

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
    game = await get_game_or_404(game_repository, game_id)
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
    await require_game_exists(game_repository, game_id)

    player_repository = PlayerRepository(db_session, principal=principal)
    await require_gm(
        player_repository,
        game_id,
        principal.id,
        "Only game masters can approve players",
    )

    player = await get_player_or_404(player_repository, game_id, user_id)
    if player.state is Player.States.ACCEPTED:
        raise ConflictException("Player already accepted")

    await player_repository.update_state(player, state=Player.States.ACCEPTED)


@games.post("/{game_id}/accept_invite", status_code=status.HTTP_204_NO_CONTENT)
async def accept_invite(
    game_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    await require_game_exists(game_repository, game_id)

    player_repository = PlayerRepository(db_session, principal=principal)
    player = await get_player_or_404(player_repository, game_id, principal.id)
    if player.state is not Player.States.INVITED:
        raise ConflictException("No pending invite for this game")

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
    game = await get_game_or_404(game_repository, game_id)

    player_repository = PlayerRepository(db_session, principal=principal)
    await require_gm(
        player_repository,
        game_id,
        principal.id,
        "Only game masters can toggle GM status",
    )

    if user_id == game.gm_id:
        raise ForbiddenException("Primary GM cannot be demoted")

    player = await get_player_or_404(player_repository, game_id, user_id)
    if player.state is not Player.States.ACCEPTED:
        raise ConflictException("Only accepted players can be made GMs")

    await player_repository.update_state(player, is_gm=not player.is_gm)


@games.delete("/{game_id}/player/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_player(
    game_id: int,
    user_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    game = await get_game_or_404(game_repository, game_id)

    player_repository = PlayerRepository(db_session, principal=principal)
    player = await get_player_or_404(player_repository, game_id, user_id)

    if user_id == game.gm_id:
        raise ForbiddenException("Primary GM cannot be removed from game")
    if (
        not await player_repository.is_gm(game_id, principal.id)
        and principal.id != user_id
    ):
        raise ForbiddenException("Only game masters can edit players")

    character_repository = CharacterRepository(db_session, principal=principal)
    await character_repository.remove_user_characters_from_game(game_id, user_id)
    await player_repository.delete_player(player)


async def _get_game_character_or_404(
    character_repository: CharacterRepository, game_id: int, character_id: int
) -> Character:
    character = await character_repository.get(character_id)
    if character is None or character.game_id != game_id:
        raise NotFoundException("Character not in game")
    return character


@games.post("/{game_id}/characters", status_code=status.HTTP_204_NO_CONTENT)
async def submit_character(
    game_id: int,
    data: schemas.SubmitCharacterInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    game = await get_game_or_404(game_repository, game_id)
    if game.retired:
        raise ForbiddenException("Game is retired")

    player_repository = PlayerRepository(db_session, principal=principal)
    player = await player_repository.get_player(game_id, principal.id)
    if player is None or player.state is not Player.States.ACCEPTED:
        raise ForbiddenException("Only players in the game can submit characters")

    character_repository = CharacterRepository(db_session, principal=principal)
    character = await character_repository.get(data.character_id)
    if character is None:
        raise NotFoundException("Character not found")
    if character.user_id != principal.id:
        raise ForbiddenException("Character not available")
    if character.game_id is not None:
        raise ConflictException("Character is already in a game")
    allowed_systems = {system.id for system in game.allowed_char_sheets}
    if character.character_sheet.system_id not in allowed_systems:
        raise ValidationError("Character sheet isn't allowed in this game")
    # Only approved characters count toward the limit, so a player can put up
    # several for the GM to pick from. GMs aren't held to it, so they can bring
    # in NPCs.
    if (
        not player.is_gm
        and await character_repository.count_approved_in_game(game_id)
        >= game.chars_per_player
    ):
        raise ForbiddenException("You cannot submit any more characters to this game")

    await character_repository.submit_to_game(character, game_id)


@games.post(
    "/{game_id}/characters/{character_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def approve_character(
    game_id: int,
    character_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    await require_game_exists(game_repository, game_id)

    player_repository = PlayerRepository(db_session, principal=principal)
    await require_gm(
        player_repository,
        game_id,
        principal.id,
        "Only game masters can approve characters",
    )

    character_repository = CharacterRepository(db_session, principal=principal)
    character = await _get_game_character_or_404(
        character_repository, game_id, character_id
    )
    if character.approved:
        raise ConflictException("Character already approved")

    await character_repository.approve(character)


@games.delete(
    "/{game_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_character(
    game_id: int,
    character_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    """Reject a pending character, remove an approved one, or (for the owner)
    withdraw either."""
    game_repository = GameRepository(db_session, principal=principal)
    await require_game_exists(game_repository, game_id)

    character_repository = CharacterRepository(db_session, principal=principal)
    character = await _get_game_character_or_404(
        character_repository, game_id, character_id
    )

    player_repository = PlayerRepository(db_session, principal=principal)
    if character.user_id != principal.id and not await player_repository.is_gm(
        game_id, principal.id
    ):
        raise ForbiddenException(
            "Only game masters can remove other players' characters"
        )

    await character_repository.remove_from_game(character)


def _deck_to_data(deck: Deck) -> schemas.DeckData:
    return schemas.DeckData(
        id=deck.id,
        label=deck.label,
        type=deck.type_id,
        size=deck.type.deck_size,
        position=deck.position,
        permissions=[permission.user_id for permission in deck.permissions],
    )


@games.get("/{game_id}/decks", response_model=schemas.GetDecksResponse)
async def get_decks(
    game_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    await require_game_exists(game_repository, game_id)

    deck_repository = DeckRepository(db_session, principal=principal)
    decks = await deck_repository.get_all_for_game(game_id)

    return schemas.GetDecksResponse(decks=[_deck_to_data(deck) for deck in decks])


@games.get("/{game_id}/decks/{deck_id}", response_model=schemas.GetDeckResponse)
async def get_deck(
    game_id: int,
    deck_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    await require_game_exists(game_repository, game_id)

    deck_repository = DeckRepository(db_session, principal=principal)
    deck = await get_deck_or_404(deck_repository, game_id, deck_id)

    return schemas.GetDeckResponse(deck=_deck_to_data(deck))


@games.post("/{game_id}/decks", response_model=schemas.CreateDecksResponse)
async def create_deck(
    game_id: int,
    request_body: schemas.CreateDecksInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    await require_game_exists(game_repository, game_id)

    player_repository = PlayerRepository(db_session, principal=principal)
    await require_gm(
        player_repository,
        game_id,
        principal.id,
        "Only game masters can create decks",
    )
    players = await player_repository.get_players_for_game(game_id, only_accepted=True)
    player_ids = [player.user_id for player in players]
    for user_id in request_body.permissions:
        if user_id not in player_ids:
            raise NotFoundException("User not in game")

    deck_repository = DeckRepository(db_session, principal=principal)
    deck = await deck_repository.create(game_id=game_id, **request_body.model_dump())

    return schemas.CreateDecksResponse(id=deck.id)


@games.patch("/{game_id}/decks/{deck_id}", response_model=schemas.CreateDecksResponse)
async def update_deck(
    game_id: int,
    deck_id: int,
    request_body: schemas.CreateDecksInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    await require_game_exists(game_repository, game_id)

    player_repository = PlayerRepository(db_session, principal=principal)
    await require_gm(
        player_repository,
        game_id,
        principal.id,
        "Only game masters can edit decks",
    )
    players = await player_repository.get_players_for_game(game_id, only_accepted=True)
    player_ids = [player.user_id for player in players]
    for user_id in request_body.permissions:
        if user_id not in player_ids:
            raise NotFoundException("User not in game")

    deck_repository = DeckRepository(db_session, principal=principal)
    deck = await get_deck_or_404(deck_repository, game_id, deck_id)

    deck = await deck_repository.update(deck, **request_body.model_dump())

    return schemas.CreateDecksResponse(id=deck.id)


@games.patch(
    "/{game_id}/decks/{deck_id}/shuffle", status_code=status.HTTP_204_NO_CONTENT
)
async def shuffle_deck(
    game_id: int, deck_id: int, db_session: DBSessionDependency, principal: Principal
):
    game_repository = GameRepository(db_session, principal=principal)
    await require_game_exists(game_repository, game_id)

    player_repository = PlayerRepository(db_session, principal=principal)
    await require_gm(
        player_repository,
        game_id,
        principal.id,
        "Only game masters can shuffle decks",
    )

    deck_repository = DeckRepository(db_session, principal=principal)
    await get_deck_or_404(deck_repository, game_id, deck_id)

    await deck_repository.shuffle(deck_id)


@games.delete("/{game_id}/decks/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck(
    game_id: int,
    deck_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game_repository = GameRepository(db_session, principal=principal)
    await require_game_exists(game_repository, game_id)

    player_repository = PlayerRepository(db_session, principal=principal)
    await require_gm(
        player_repository,
        game_id,
        principal.id,
        "Only game masters can delete decks",
    )

    deck_repository = DeckRepository(db_session, principal=principal)
    await get_deck_or_404(deck_repository, game_id, deck_id)

    await deck_repository.delete(deck_id)


async def _require_gm_game(
    db_session: DBSessionDependency,
    principal: Principal,
    game_id: int,
    message: str,
    *,
    write: bool = False,
) -> None:
    """404 for a missing game, 403 unless the principal is one of its GMs and,
    for writes, unless the game is still active."""
    game_repository = GameRepository(db_session, principal=principal)
    game = await get_game_or_404(game_repository, game_id)
    await require_gm(
        PlayerRepository(db_session, principal=principal),
        game_id,
        principal.id,
        message,
    )
    if write:
        require_not_retired(game)


@games.get("/{game_id}/images", response_model=list[npc_schemas.GameImageData])
async def get_game_images(
    game_id: int, db_session: DBSessionDependency, principal: Principal
):
    await _require_gm_game(
        db_session, principal, game_id, "Only game masters can see the image library"
    )
    npc_repository = GameNPCRepository(db_session, principal=principal)
    return [
        build_image_data(image) for image in await npc_repository.get_images(game_id)
    ]


async def _store_game_image(
    npc_repository: GameNPCRepository, game_id: int, contents: bytes
) -> npc_schemas.GameImageData:
    image, ext = process_avatar_upload(contents)
    game_image = await npc_repository.create_image(game_id, ext)
    save_avatar(image, Path(configs.AVATARS_DIR + "/npcs") / f"{game_image.id}.{ext}")
    return build_image_data(game_image)


@games.post("/{game_id}/images", response_model=npc_schemas.GameImageData)
async def upload_game_image(
    game_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
    image: UploadFile = File(...),
):
    await _require_gm_game(
        db_session,
        principal,
        game_id,
        "Only game masters can add images",
        write=True,
    )
    return await _store_game_image(
        GameNPCRepository(db_session, principal=principal),
        game_id,
        await image.read(),
    )


@games.post("/{game_id}/images/link", response_model=npc_schemas.GameImageData)
async def link_game_image(
    game_id: int,
    data: npc_schemas.LinkImageInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    """Download the image at a URL once and keep our own copy of it."""
    await _require_gm_game(
        db_session,
        principal,
        game_id,
        "Only game masters can add images",
        write=True,
    )
    contents = await fetch_remote_image(data.url)
    return await _store_game_image(
        GameNPCRepository(db_session, principal=principal), game_id, contents
    )


@games.get("/{game_id}/npcs", response_model=list[npc_schemas.NPCData])
async def get_game_npcs(
    game_id: int, db_session: DBSessionDependency, principal: Principal
):
    await _require_gm_game(
        db_session, principal, game_id, "Only game masters can see NPCs"
    )
    npc_repository = GameNPCRepository(db_session, principal=principal)
    return [build_npc_data(npc) for npc in await npc_repository.get_npcs(game_id)]


@games.patch("/{game_id}/npcs/{npc_id}", response_model=npc_schemas.NPCData)
async def update_game_npc(
    game_id: int,
    npc_id: int,
    data: npc_schemas.UpdateNPCInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    """Rename an NPC and/or change its image. Every post that used it changes too."""
    await _require_gm_game(
        db_session,
        principal,
        game_id,
        "Only game masters can edit NPCs",
        write=True,
    )
    npc_repository = GameNPCRepository(db_session, principal=principal)
    npc = await get_npc_or_404(npc_repository, game_id, npc_id)

    if "name" in data.model_fields_set and data.name is None:
        raise ValidationError("An NPC needs a name")
    name = data.name if data.name is not None else npc.name
    image = npc.image
    if "image_id" in data.model_fields_set:
        image = (
            await require_game_image(npc_repository, game_id, data.image_id)
            if data.image_id is not None
            else None
        )

    npc = await npc_repository.update(npc, name, image)
    return build_npc_data(npc)


@games.delete("/{game_id}/npcs/{npc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_game_npc(
    game_id: int,
    npc_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    """Retire an NPC. Posts that used it keep showing it."""
    await _require_gm_game(
        db_session,
        principal,
        game_id,
        "Only game masters can delete NPCs",
        write=True,
    )
    npc_repository = GameNPCRepository(db_session, principal=principal)
    npc = await get_npc_or_404(npc_repository, game_id, npc_id)
    await npc_repository.delete(npc)


@games.patch("/{game_id}/retire", status_code=status.HTTP_204_NO_CONTENT)
async def toggle_retire_game(
    game_id: int, db_session: DBSessionDependency, principal: Principal
):
    game_repository = GameRepository(db_session, principal=principal)
    game = await get_game_or_404(game_repository, game_id)

    if principal.id != game.gm_id:
        raise ForbiddenException("Only the primary GM can retire a game")

    await game_repository.toggle_retire(game)
