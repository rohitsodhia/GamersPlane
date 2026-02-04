from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.legacy.base import LegacyBase

if TYPE_CHECKING:
    from app.models.legacy import Game, User


class ForumGroup(LegacyBase):
    __tablename__ = "forum_groups"

    id: Mapped[int] = mapped_column("groupID", primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[bool] = mapped_column(default=True)
    owner_id: Mapped[int] = mapped_column("ownerID", ForeignKey("users.userID"))
    owner: Mapped["User"] = relationship()
    game_id: Mapped[int] = mapped_column(
        "gameID", ForeignKey("games.gameID"), nullable=True
    )
    game: Mapped["Game"] = relationship(foreign_keys=[game_id])
