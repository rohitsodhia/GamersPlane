from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GameAllowedSystem(Base):
    __tablename__ = "game_allowed_systems"

    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("systems.id"), primary_key=True)
