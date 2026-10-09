"""Server-side redaction of post rolls and draws.

Anything a viewer isn't allowed to see is removed from the response here, never
sent and hidden client-side.
"""

from app.models import PostDraw, PostRoll
from app.posts.schemas import PostDrawData, PostRollData


def summarize_roll_result(roll_type: str, result: dict) -> dict:
    """The part of a roll result that doesn't reveal the individual dice.

    Used for viewers who may see the outcome of a ``hide_dice`` roll but not its
    pool or faces:

    - basic, fate, fengshui: ``{"total"}``
    - starwarsffg: ``{"net_success", "net_advantage", "triumph", "despair"}``. The
      net values are the outcome; triumph and despair are shown because they
      trigger effects beyond the net result. Per-icon totals (successes, threats,
      ...) are withheld, as they'd expose the pool.
    """
    if roll_type == "starwarsffg":
        totals = result["totals"]
        return {
            "net_success": result["net_success"],
            "net_advantage": result["net_advantage"],
            "triumph": totals["triumph"],
            "despair": totals["despair"],
        }
    return {"total": result["total"]}


def redact_roll(roll: PostRoll, *, full_view: bool) -> PostRollData:
    """Build the response for ``roll`` as seen by one viewer.

    ``full_view`` is True for the post's author and for moderators of its forum;
    they see everything, flags included. Everyone else (anonymous viewers too)
    gets the roll with these fields removed:

    - ``hide_reason``: ``reason`` is ``None``.
    - ``hide_dice``: ``input`` and ``options`` are ``None`` (they'd reveal the
      pool), and ``result`` is replaced by ``summary`` (see
      ``summarize_roll_result``), unless ``hide_result`` is also set.
    - ``hide_result``: ``result`` and ``summary`` are ``None``. The input stays
      visible unless ``hide_dice`` is set, so the UI can show blank dice.

    The flags themselves are always sent.
    """
    hide_dice = roll.hide_dice and not full_view
    hide_result = roll.hide_result and not full_view
    result = None if hide_dice or hide_result else roll.result
    summary = None
    if hide_dice and not hide_result:
        summary = summarize_roll_result(roll.type, roll.result)
    return PostRollData(
        id=roll.id,
        type=roll.type,  # type: ignore[arg-type]
        reason=None if roll.hide_reason and not full_view else roll.reason,
        input=None if hide_dice else roll.input,
        options=None if hide_dice else roll.options,
        result=result,
        summary=summary,
        hide_reason=roll.hide_reason,
        hide_dice=roll.hide_dice,
        hide_result=roll.hide_result,
    )


def redact_draw(draw: PostDraw, *, is_author: bool) -> PostDrawData:
    """Build the response for ``draw`` as seen by one viewer.

    Only the post's author sees every card. Everyone else, moderators and GMs
    included, sees just the cards the author revealed; the rest are ``None``.
    """
    return PostDrawData(
        id=draw.id,
        deck_id=draw.deck_id,
        deck_label=draw.deck_label,
        deck_type=draw.deck_type,
        reason=draw.reason,
        cards=[
            card if is_author or revealed else None
            for card, revealed in zip(draw.cards, draw.revealed, strict=True)
        ],
        revealed=list(draw.revealed),
    )
