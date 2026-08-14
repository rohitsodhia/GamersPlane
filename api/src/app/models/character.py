from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models import System


class Character(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "characters"

    class Type(LabelEnum):
        PC = "pc", "PC"
        NPC = "npc", "NPC"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    system_id: Mapped[int] = mapped_column(ForeignKey("systems.id"))
    system: Mapped[System] = relationship(lazy="joined")
    type: Mapped[Type] = mapped_column(LabelEnumType(Type, String(5)))
    data: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
