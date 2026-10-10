from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PostRoll(Base, TimestampMixin):
    """A dice roll attached to a post.

    Rolls are their own rows, keyed to the post, so editing a post's body can never
    detach or replace them. Nothing deletes or rerolls one.
    """

    __tablename__ = "post_rolls"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    # A key of ``app.tools.dice.ROLL_TYPES``.
    type: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(default="")
    # The roll string as entered.
    input: Mapped[str]
    # The system-relevant options the roll used (e.g. ``{"reroll_aces": true}``).
    options: Mapped[dict] = mapped_column(JSON())
    # The ``RollResult.model_dump()``.
    result: Mapped[dict] = mapped_column(JSON())
    hide_reason: Mapped[bool] = mapped_column(default=False)
    hide_dice: Mapped[bool] = mapped_column(default=False)
    hide_result: Mapped[bool] = mapped_column(default=False)
