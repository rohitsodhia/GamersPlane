from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class SystemGenre(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "system_genres"

    system_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("systems.id"), primary_key=True
    )
    genre_id: Mapped[int] = mapped_column(ForeignKey("genres.id"), primary_key=True)
