from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.legacy.base import LegacyBase

if TYPE_CHECKING:
    from app.models.legacy import Game, User


class Player(LegacyBase):
    __tablename__ = "players"

    game_id: Mapped[int] = mapped_column(
        "gameID", ForeignKey("games.gameID"), primary_key=True
    )
    game: Mapped["Game"] = relationship("Game", foreign_keys=[game_id])
    user_id: Mapped[int] = mapped_column(
        "userID", ForeignKey("users.userID"), primary_key=True
    )
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    approved: Mapped[bool] = mapped_column(default=False)
    is_gm: Mapped[bool] = mapped_column("isGM", default=False)
