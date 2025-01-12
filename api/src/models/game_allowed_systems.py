from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class GameAllowedSystem(Base):
    __tablename__ = "user_roles"

    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("systems.id"), primary_key=True)
