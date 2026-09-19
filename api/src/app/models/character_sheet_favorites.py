from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models import CharacterSheet


class CharacterSheetFavorite(Base, TimestampMixin):
    __tablename__ = "favorite_character_sheets"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    character_sheet_id: Mapped[int] = mapped_column(
        ForeignKey("character_sheets.id"), primary_key=True
    )
    character_sheet: Mapped[CharacterSheet] = relationship(
        "CharacterSheet", foreign_keys=[character_sheet_id]
    )
