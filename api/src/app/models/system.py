from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import session_manager
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models import Genre, Publisher


class System(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "systems"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    sort_name: Mapped[str] = mapped_column(String(40))
    publisher_id: Mapped[int] = mapped_column(ForeignKey("publishers.id"))
    publisher: Mapped["Publisher"] = relationship()
    genres: Mapped[List["Genre"]] = relationship(secondary="system_genres")
    basics: Mapped[dict | None] = mapped_column(JSON())
    has_char_sheet: Mapped[bool]
    enabled: Mapped[bool]

    @staticmethod
    def get_all() -> "list[System]":
        with session_manager.session() as db_session:
            systems = db_session.scalars(select(System).order_by("sort_name"))
            return [system for system in systems]

    @staticmethod
    def get(system_id: str | None = None) -> "System | None":
        with session_manager.session() as db_session:
            system = db_session.scalar(
                select(System).where(System.id == system_id).limit(1)
            )
            return system
