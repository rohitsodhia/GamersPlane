import logging
from collections.abc import Iterable
from pathlib import Path

from fastapi import BackgroundTasks
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs import configs
from app.exceptions import ForbiddenException, NotFoundException, ValidationError
from app.forums.functions import filter_readable_forum_ids
from app.games import schemas
from app.middleware import Principal
from app.models import Deck, Game, Player, UserMeta
from app.helpers.email import get_template, send_email
from app.repositories import (
    DeckRepository,
    GameRepository,
    PlayerRepository,
    ReadTrackingRepository,
    SystemRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)


async def send_new_game_email(
    recipients: list[str],
    *,
    game_id: int,
    title: str,
    num_players: int,
    system_id: str,
    system_name: str,
    gm_id: int,
    gm_username: str,
) -> None:
    """Mail the LFG opt-ins about a new game. Takes plain values only: it runs
    as a background task, after the request's DB session is gone."""
    # Titles are stored with newlines as <br>
    title = title.replace("<br>", " ")
    content = get_template(
        "games/templates/new_game.html",
        game_id=game_id,
        title=title,
        num_players=num_players,
        system_id=system_id,
        system_name=system_name,
        gm_id=gm_id,
        gm_username=gm_username,
    )
    await send_email(
        configs.CONTACT_EMAIL,
        f"New {system_name} Game: {title}",
        content,
        bcc=recipients,
        mass=True,
    )


GM_PREFERENCE_LABEL = "Receive GM emails?"
PLAYER_PREFERENCE_LABEL = "Receive game emails?"
ACTIVITY_TEMPLATE = "games/templates/game_activity.html"
INVITE_TEMPLATE = "games/templates/game_invite.html"


async def send_game_activity_email(
    recipients: list[str],
    *,
    game_id: int,
    title: str,
    system_id: str,
    system_name: str,
    subject: str,
    headline: str,
    message: str = "",
    preference_label: str,
    template: str = ACTIVITY_TEMPLATE,
    intro: str = "member",
    inviter_username: str = "",
) -> None:
    """Mail each recipient (one message apiece) about something that happened in a
    game. Takes plain values only: it runs as a background task, after the
    request's DB session is gone. ``message`` is plain text; the template
    escapes it. ``intro`` picks the activity template's opening sentence:
    "member" for someone in the game, "former" for someone who isn't (or
    is no longer). ``inviter_username`` is only used by the invite template."""
    title = title.replace("<br>", " ")
    content = get_template(
        template,
        game_id=game_id,
        title=title,
        system_id=system_id,
        system_name=system_name,
        headline=headline,
        message=message,
        preference_label=preference_label,
        intro=intro,
        inviter_username=inviter_username,
    )
    for recipient in recipients:
        await send_email(recipient, f"[{title}] {subject}", content)


async def _queue_game_activity_email(
    background_tasks: BackgroundTasks,
    db_session: AsyncSession,
    game: Game,
    recipients: list[str],
    *,
    subject: str,
    headline: str,
    message: str = "",
    preference_label: str,
    template: str = ACTIVITY_TEMPLATE,
    intro: str = "member",
    inviter_username: str = "",
) -> None:
    if not recipients:
        return
    system = await SystemRepository(db_session).get_by_id(game.system_id)
    background_tasks.add_task(
        send_game_activity_email,
        recipients,
        game_id=game.id,
        title=game.title,
        system_id=game.system_id,
        system_name=system.name if system else game.system_id,
        subject=subject,
        headline=headline,
        message=message,
        preference_label=preference_label,
        template=template,
        intro=intro,
        inviter_username=inviter_username,
    )


def _log_title(game: Game) -> str:
    return game.title.replace("<br>", " ")


async def queue_gm_email(
    background_tasks: BackgroundTasks,
    db_session: AsyncSession,
    game: Game,
    principal: Principal,
    *,
    exclude_user_ids: Iterable[int],
    subject: str,
    headline: str,
    message: str,
) -> None:
    """Tell the game's GMs (primary and co-GMs, minus ``exclude_user_ids``)
    something happened, honoring their gmMail preference. Resolves recipients
    now, inside the request, and schedules the send."""
    if not configs.EMAIL_ENABLED:
        logger.info(
            "Email disabled; would have mailed game %s GMs: [%s] %s",
            game.id,
            _log_title(game),
            subject,
        )
        return
    excluded = set(exclude_user_ids)
    gm_ids = await PlayerRepository(db_session, principal=principal).get_gm_ids(game.id)
    recipients = await UserRepository(db_session).get_mail_recipients(
        {*gm_ids, game.gm_id} - excluded, UserMeta.MetaKeys.GM_MAIL
    )
    await _queue_game_activity_email(
        background_tasks,
        db_session,
        game,
        recipients,
        subject=subject,
        headline=headline,
        message=message,
        preference_label=GM_PREFERENCE_LABEL,
    )


async def queue_player_email(
    background_tasks: BackgroundTasks,
    db_session: AsyncSession,
    game: Game,
    principal: Principal,
    user_id: int,
    *,
    subject: str,
    headline: str,
    message: str = "",
    to_gms: bool = False,
    template: str = ACTIVITY_TEMPLATE,
    intro: str = "member",
    inviter_username: str = "",
) -> None:
    """Tell one player what the acting GM (``principal``) did, honoring their
    gameMail preference. Never mails the actor. A player who is themselves a GM
    is skipped unless ``to_gms`` is set (being made, or removed as, a GM).
    Pass ``intro="former"`` when the recipient isn't in the game."""
    if user_id == principal.id:
        return
    if not configs.EMAIL_ENABLED:
        logger.info(
            "Email disabled; would have mailed game %s player %s: [%s] %s",
            game.id,
            user_id,
            _log_title(game),
            subject,
        )
        return
    if not to_gms:
        player = await PlayerRepository(db_session, principal=principal).get_player(
            game.id, user_id
        )
        if user_id == game.gm_id or (player is not None and player.is_gm):
            return
    recipients = await UserRepository(db_session).get_mail_recipients(
        [user_id], UserMeta.MetaKeys.GAME_MAIL
    )
    await _queue_game_activity_email(
        background_tasks,
        db_session,
        game,
        recipients,
        subject=subject,
        headline=headline,
        message=message,
        preference_label=PLAYER_PREFERENCE_LABEL,
        template=template,
        intro=intro,
        inviter_username=inviter_username,
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


def background_path(filename: str) -> Path:
    return Path(configs.BACKGROUNDS_DIR) / filename


def get_background(options: dict | None) -> schemas.BackgroundOptions | None:
    """The stored background, or None if there isn't one or it isn't valid."""
    if not options or not options.get("background"):
        return None
    try:
        return schemas.BackgroundOptions.model_validate(options["background"])
    except PydanticValidationError:
        return None


def build_background_data(
    background: schemas.BackgroundOptions,
) -> schemas.BackgroundData:
    return schemas.BackgroundData(
        **background.model_dump(exclude={"image"}),
        url=f"{configs.BACKGROUNDS_ROOT}/{background.image}",
    )


def build_advanced_options_data(
    options: dict | None,
) -> schemas.AdvancedOptionsData | None:
    if options is None:
        return None
    background = get_background(options)
    return schemas.AdvancedOptionsData(
        background=build_background_data(background) if background else None
    )


def merge_advanced_options(
    stored: dict | None, incoming: schemas.AdvancedOptionsInput | None
) -> dict | None:
    """Apply a client's options to the stored ones. Clients only set how the
    background is shown; the image itself comes from the upload endpoint, so
    it's kept, and a background can't be configured before one is uploaded."""
    options = dict(stored or {})
    if incoming is not None and incoming.background is not None:
        existing = get_background(options)
        if existing is None:
            raise ValidationError("Upload a background image first")
        options["background"] = existing.model_copy(
            update=incoming.background.model_dump()
        ).model_dump()
    return options or None
