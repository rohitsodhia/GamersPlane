from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models import Character


class CharacterAvatar(Base, TimestampMixin):
    __tablename__ = "character_avatars"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"))
    character: Mapped[Character] = relationship(back_populates="avatars")
    ext: Mapped[str] = mapped_column(String(5))
    is_primary: Mapped[bool] = mapped_column(Boolean(), default=False)
