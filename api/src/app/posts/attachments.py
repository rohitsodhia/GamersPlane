"""Rolls and deck draws attached to posts: validating, performing and saving them.

A request is handled in two steps so a failure leaves nothing half-done:
``plan_attachments`` checks every permission, rolls the dice and locks and
sanity-checks the decks without persisting anything; ``save_attachments`` then
stores the rolls and takes the cards.
"""

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ForbiddenException, NotFoundException, ValidationError
from app.forums.permissions import ForumPermissions, Verbs
from app.models import Deck, Forum, Post, Thread, User
from app.posts.schemas import NewDrawInput, NewRollInput
from app.repositories import DeckRepository, PlayerRepository, PostRepository
from app.tools.dice import get_roll

# The options each dice system reads; others are dropped before storing.
SYSTEM_OPTIONS: dict[str, tuple[str, ...]] = {
    "basic": ("reroll_aces",),
    "fate": ("modifier",),
    "fengshui": ("roll_type",),
    "starwarsffg": (),
}


@dataclass
class PlannedRoll:
    data: NewRollInput
    input: str
    options: dict
    result: dict


@dataclass
class PlannedDraw:
    deck: Deck
    count: int
    reason: str


@dataclass
class PostAttachments:
    rolls: list[PlannedRoll] = field(default_factory=list)
    draws: list[PlannedDraw] = field(default_factory=list)


def _perform_roll(data: NewRollInput) -> PlannedRoll:
    roll_string = data.roll.strip()
    if not roll_string:
        raise ValidationError("Roll can't be empty")
    options = {name: getattr(data.options, name) for name in SYSTEM_OPTIONS[data.type]}
    try:
        result = get_roll(data.type, roll_string, **options).result
    except ValueError as e:
        raise ValidationError(str(e))
    assert result is not None
    dumped = result.model_dump()
    # A string of unrecognised tokens parses to nothing rather than erroring.
    if not (dumped.get("groups", True) and dumped.get("rolls", True)):
        raise ValidationError(f"Nothing to roll in '{roll_string}'")
    return PlannedRoll(data, roll_string, options, dumped)


async def plan_attachments(
    db_session: AsyncSession,
    principal: User,
    forum: Forum,
    permissions: ForumPermissions,
    thread_options: Thread.Options,
    rolls: list[NewRollInput],
    draws: list[NewDrawInput],
) -> PostAttachments:
    """Validate and perform (but don't save) the requested rolls and draws.

    ``thread_options`` are the options of the thread being posted in (or, for a
    new thread, being created). Raises ``ForbiddenException`` when the thread or
    the principal's permissions don't allow rolls/draws or the principal can't
    draw from a deck; ``ValidationError`` for a bad roll string, a deck named
    twice or too few cards left; ``NotFoundException`` for a deck that doesn't
    exist in the forum's game (as ``get_deck_or_404`` does).

    Draws lock their decks' rows, so keep the request's transaction short.
    """
    planned = PostAttachments()

    if rolls:
        if not thread_options.allow_rolls:
            raise ForbiddenException("Rolls aren't allowed in this thread")
        if not permissions.has(forum, Verbs.FORUM_ADD_ROLLS):
            raise ForbiddenException("You can't add rolls in this forum")
        planned.rolls = [_perform_roll(data) for data in rolls]

    if draws:
        if not thread_options.allow_draws:
            raise ForbiddenException("Draws aren't allowed in this thread")
        if not permissions.has(forum, Verbs.FORUM_ADD_DRAWS):
            raise ForbiddenException("You can't add draws in this forum")
        if forum.game_id is None:
            raise ForbiddenException("Draws are only available in game forums")
        deck_ids = [draw.deck_id for draw in draws]
        if len(set(deck_ids)) != len(deck_ids):
            raise ValidationError("Each deck can only be drawn from once per post")

        deck_repository = DeckRepository(db_session, principal=principal)
        is_gm = await PlayerRepository(db_session, principal=principal).is_gm(
            forum.game_id, principal.id
        )
        # Lock in id order so two posts drawing from several decks can't deadlock.
        decks: dict[int, Deck] = {}
        for deck_id in sorted(deck_ids):
            deck = await deck_repository.get_for_update(deck_id)
            if deck is None or deck.game_id != forum.game_id:
                raise NotFoundException("Deck not found")
            if not is_gm and not await deck_repository.can_draw(deck_id, principal.id):
                raise ForbiddenException(f"You can't draw from {deck.label}")
            decks[deck_id] = deck

        for draw in draws:
            deck = decks[draw.deck_id]
            remaining = len(deck.order) - deck.position
            if draw.count > remaining:
                raise ValidationError(
                    f"Not enough cards left in {deck.label} "
                    f"({remaining} remaining, {draw.count} requested)"
                )
            reason = draw.reason.strip()
            if not reason:
                raise ValidationError("A draw needs a reason")
            planned.draws.append(PlannedDraw(deck, draw.count, reason))

    return planned


async def save_attachments(
    db_session: AsyncSession,
    principal: User,
    post: Post,
    attachments: PostAttachments,
) -> None:
    """Store planned rolls and take the planned draws' cards off their decks."""
    post_repository = PostRepository(db_session, principal=principal)
    for roll in attachments.rolls:
        await post_repository.add_roll(
            post.id,
            roll.data.type,
            roll.data.reason,
            roll.input,
            roll.options,
            roll.result,
            roll.data.hide_reason,
            roll.data.hide_dice,
            roll.data.hide_result,
        )

    deck_repository = DeckRepository(db_session, principal=principal)
    for draw in attachments.draws:
        cards = await deck_repository.draw(draw.deck, draw.count)
        await post_repository.add_draw(post.id, draw.deck, draw.reason, cards)
