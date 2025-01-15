from typing import TYPE_CHECKING

from models.base import Base, SoftDeleteMixin, TimestampMixin
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import String

if TYPE_CHECKING:
    from models import Game, User


class ForumGroup(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "forum_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[bool] = mapped_column(default=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owner: Mapped["User"] = relationship()
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    game: Mapped["Game"] = relationship()
