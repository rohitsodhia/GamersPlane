from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PostDraw(Base, TimestampMixin):
    """Cards drawn from a game deck and attached to a post.

    The deck's label and type are copied at draw time, so the draw outlives the
    deck (``deck_id`` is nulled if the deck is deleted).
    """

    __tablename__ = "post_draws"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    deck_id: Mapped[int | None] = mapped_column(
        ForeignKey("decks.id", ondelete="SET NULL"), nullable=True
    )
    deck_label: Mapped[str]
    deck_type: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str]
    # Card ids, in the order drawn.
    cards: Mapped[list[int]] = mapped_column(JSON())
    # Parallel to ``cards``: whether the author has shown each card to others.
    revealed: Mapped[list[bool]] = mapped_column(JSON())
