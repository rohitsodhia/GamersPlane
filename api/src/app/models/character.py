from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models import CharacterSheet, User


class Character(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "characters"

    class Type(LabelEnum):
        PC = "pc", "PC"
        NPC = "npc", "NPC"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship()
    character_sheet_id: Mapped[int] = mapped_column(ForeignKey("character_sheets.id"))
    character_sheet: Mapped[CharacterSheet] = relationship()
    label: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column(nullable=True)
    type: Mapped[Type] = mapped_column(LabelEnumType(Type, String(5)))
    values: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
