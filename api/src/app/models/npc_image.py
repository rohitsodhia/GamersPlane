from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NPCImage(Base, TimestampMixin):
    """An image in a quick NPC library, owned by a game (shared by its players) or
    by a user (their personal library). One image can serve many NPCs."""

    __tablename__ = "npc_images"
    __table_args__ = (
        CheckConstraint(
            "(game_id IS NULL) <> (user_id IS NULL)",
            name="ck_npc_images_one_owner",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int | None] = mapped_column(
        ForeignKey("games.id"), index=True, nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=True
    )
    ext: Mapped[str] = mapped_column(String(5))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
