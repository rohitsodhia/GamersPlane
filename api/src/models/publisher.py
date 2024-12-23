from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, SoftDeleteMixin, TimestampMixin


class Publisher(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "publishers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    website: Mapped[str | None] = mapped_column(String(200))
