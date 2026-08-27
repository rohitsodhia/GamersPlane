from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models import Character, Game


class FavoriteGame(Base, TimestampMixin):
    __tablename__ = "favorite_games"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), primary_key=True)
    game: Mapped[Game] = relationship("Game", foreign_keys=[game_id])


class FavoriteCharacter(Base, TimestampMixin):
    __tablename__ = "favorite_characters"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id"), primary_key=True
    )
    character: Mapped[Character] = relationship(
        "Character", foreign_keys=[character_id]
    )
