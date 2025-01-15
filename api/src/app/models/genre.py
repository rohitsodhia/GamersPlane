from models.base import Base, SoftDeleteMixin, TimestampMixin
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class Genre(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    genre: Mapped[str] = mapped_column(String(40))
