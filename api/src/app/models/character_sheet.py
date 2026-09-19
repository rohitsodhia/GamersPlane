from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models import System, User


class CharacterSheet(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "character_sheets"

    class Status(LabelEnum):
        PRIVATE = "private", "Private"  # creator only
        PUBLIC = "public", "Public"  # anyone can use
        OFFICIAL = "official", "Official"  # site-blessed, in the picker
        RETIRED = "retired", "Retired"  # superseded by a newer version

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    creator: Mapped[User] = relationship()
    version: Mapped[int] = mapped_column(default=1)
    root_id: Mapped[int | None] = mapped_column(
        ForeignKey("character_sheets.id"), index=True
    )
    name: Mapped[str] = mapped_column()
    system_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("systems.id"), index=True
    )
    system: Mapped[System] = relationship()
    layout: Mapped[dict] = mapped_column(JSON(), default=dict, deferred=True)
    status: Mapped[Status] = mapped_column(
        LabelEnumType(Status, String(12)), default=Status.PRIVATE, index=True
    )

    @property
    def is_public(self) -> bool:
        return self.status in (self.Status.PUBLIC, self.Status.OFFICIAL)
