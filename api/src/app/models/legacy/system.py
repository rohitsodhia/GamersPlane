from typing import TYPE_CHECKING

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.legacy.base import LegacyBase

if TYPE_CHECKING:
    pass


class System(LegacyBase):
    __tablename__ = "systems"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    sort_name: Mapped[str] = mapped_column("sortName", String(40))
    enabled: Mapped[bool]
    angular: Mapped[bool]
    genres: Mapped[list | None] = mapped_column(JSON(), nullable=True)
    publisher: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    basics: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    has_char_sheet: Mapped[bool] = mapped_column("hasCharSheet", default=1)
    lfg: Mapped[int] = mapped_column(default=0)
