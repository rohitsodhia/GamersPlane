from app.exceptions import ForbiddenException, NotFoundException, ValidationError
from app.models import Deck, Game, GameImage, GameNPC, Player
from app.repositories import (
    DeckRepository,
    GameNPCRepository,
    GameRepository,
    PlayerRepository,
)


async def get_game_or_404(game_repository: GameRepository, game_id: int) -> Game:
    game = await game_repository.get(game_id)
    if not game:
        raise NotFoundException("Game not found")
    return game


async def require_game_exists(game_repository: GameRepository, game_id: int) -> None:
    if not await game_repository.exists(game_id):
        raise NotFoundException("Game not found")


async def get_player_or_404(
    player_repository: PlayerRepository, game_id: int, user_id: int
) -> Player:
    player = await player_repository.get_player(game_id, user_id)
    if player is None:
        raise NotFoundException("Player not in game")
    return player


async def require_gm(
    player_repository: PlayerRepository,
    game_id: int,
    principal_id: int,
    message: str,
) -> None:
    if not await player_repository.is_gm(game_id, principal_id):
        raise ForbiddenException(message)


def require_not_retired(game: Game) -> None:
    if game.retired:
        raise ForbiddenException("Game is retired")


async def get_npc_or_404(
    npc_repository: GameNPCRepository, game_id: int, npc_id: int
) -> GameNPC:
    npc = await npc_repository.get_npc(npc_id)
    if not npc or npc.game_id != game_id:
        raise NotFoundException("NPC not found")
    return npc


async def require_game_image(
    npc_repository: GameNPCRepository, game_id: int, image_id: int
) -> GameImage:
    """An image from the game's library, as named in a request body."""
    image = await npc_repository.get_image(image_id)
    if not image or image.game_id != game_id:
        raise ValidationError("That image isn't in this game's library")
    return image


async def get_deck_or_404(
    deck_repository: DeckRepository, game_id: int, deck_id: int
) -> Deck:
    deck = await deck_repository.get_by_id(deck_id)
    if not deck or deck.game_id != game_id:
        raise NotFoundException("Deck not found")
    return deck
