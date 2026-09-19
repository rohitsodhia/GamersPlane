from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GameAllowedSystem(Base):
    __tablename__ = "game_allowed_char_sheets"

    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), primary_key=True)
    system_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("systems.id"), primary_key=True
    )
