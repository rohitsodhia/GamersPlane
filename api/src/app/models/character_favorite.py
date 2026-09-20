from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models import Character


class CharacterFavorite(Base, TimestampMixin):
    __tablename__ = "character_favorites"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id"), primary_key=True
    )
    character: Mapped[Character] = relationship(
        "Character", foreign_keys=[character_id]
    )
