from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.legacy import Game, User
from app.models.legacy.base import LegacyBase


class GameFavorite(LegacyBase):
    __tablename__ = "games_favorites"

    game_id: Mapped[int] = mapped_column(
        "gameID", ForeignKey("games.gameID"), primary_key=True
    )
    game: Mapped[Game] = relationship(Game, foreign_keys=[game_id])
    user_id: Mapped[int] = mapped_column(
        "userID", ForeignKey("users.userID"), primary_key=True
    )
    user: Mapped[User] = relationship(User, foreign_keys=[user_id])
