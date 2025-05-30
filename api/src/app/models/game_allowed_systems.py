from models.base import Base
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class GameAllowedSystem(Base):
    __tablename__ = "user_roles"

    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("systems.id"), primary_key=True)
