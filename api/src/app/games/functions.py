from app.exceptions import ForbiddenException, NotFoundException
from app.models import Deck, Game, Player
from app.repositories import DeckRepository, GameRepository, PlayerRepository


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


async def get_deck_or_404(
    deck_repository: DeckRepository, game_id: int, deck_id: int
) -> Deck:
    deck = await deck_repository.get_by_id(deck_id)
    if not deck or deck.game_id != game_id:
        raise NotFoundException("Deck not found")
    return deck
