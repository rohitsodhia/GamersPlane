from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from models import Genre, Publisher


class System(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "systems"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    sort_name: Mapped[str] = mapped_column(String(40))
    publisher_id: Mapped[int] = mapped_column(ForeignKey("publishers.id"))
    publisher: Mapped["Publisher"] = relationship()
    genres: Mapped[List["Genre"]] = relationship(secondary="system_genres")
    basics: Mapped[Optional[JSON]]
    has_char_sheet: Mapped[bool]
    enabled: Mapped[bool]
