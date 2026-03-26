from typing import TYPE_CHECKING

from sqlalchemy import JSON, String
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column

from app.models.legacy.base import LegacyBase

if TYPE_CHECKING:
    pass


class System(MappedAsDataclass, AsyncAttrs, LegacyBase):
    __tablename__ = "systems"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    sort_name: Mapped[str] = mapped_column("sortName", String(40))
    enabled: Mapped[bool]
    angular: Mapped[bool]
    publisher: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    genres: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    basics: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    has_char_sheet: Mapped[bool] = mapped_column("hasCharSheet")
    lfg: Mapped[int]
