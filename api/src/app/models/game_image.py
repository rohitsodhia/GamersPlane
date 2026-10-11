from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class GameImage(Base, TimestampMixin):
    """An image in a game's quick NPC library. One image can serve many NPCs."""

    __tablename__ = "game_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    ext: Mapped[str] = mapped_column(String(5))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
