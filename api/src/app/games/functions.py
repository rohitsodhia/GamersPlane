from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ForbiddenException, NotFoundException
from app.forums.functions import filter_readable_forum_ids
from app.middleware import Principal
from app.models import Deck, Game, Player
from app.repositories import (
    DeckRepository,
    GameRepository,
    PlayerRepository,
    ReadTrackingRepository,
)


async def unread_game_ids(
    db_session: AsyncSession, principal: Principal, games: list[Game]
) -> set[int]:
    """The games whose root forum has unread posts for the principal, counting
    their readable subforums as the forum index does. A game whose root forum
    isn't readable is never unread."""
    if not games:
        return set()
    forum_ids = await GameRepository(
        db_session, principal=principal
    ).get_game_forum_ids([game.id for game in games])
    readable_ids = await filter_readable_forum_ids(db_session, principal, forum_ids)
    unread_forum_ids = await ReadTrackingRepository(
        db_session, principal=principal
    ).unread_forum_ids(readable_ids)
    return {game.id for game in games if game.root_forum_id in unread_forum_ids}


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


async def get_deck_or_404(
    deck_repository: DeckRepository, game_id: int, deck_id: int
) -> Deck:
    deck = await deck_repository.get_by_id(deck_id)
    if not deck or deck.game_id != game_id:
        raise NotFoundException("Deck not found")
    return deck
