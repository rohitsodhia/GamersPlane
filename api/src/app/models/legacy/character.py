from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.legacy.base import LegacyBase

if TYPE_CHECKING:
    from app.models.legacy import Game, System, User


class Character(LegacyBase):
    __tablename__ = "characters"

    class Type(Enum):
        PC = "pc"
        NPC = "npc"

    id: Mapped[int] = mapped_column("characterID", primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column("userID", ForeignKey("users.userID"))
    user: Mapped["User"] = relationship("User", back_populates="characters")
    label: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    charType: Mapped[Type]
    system_id: Mapped[int] = mapped_column("system", ForeignKey("systems.id"))
    system: Mapped["System"] = relationship()
    data: Mapped[dict] = mapped_column(JSON())
    game_id: Mapped[int] = mapped_column("gameID", ForeignKey("games.gameID"))
    game: Mapped["Game"] = relationship()
    approved: Mapped[bool] = mapped_column(default=False)
    in_library: Mapped[bool] = mapped_column("inLibrary", default=False)
    library_views: Mapped[int] = mapped_column("libraryViews", default=0)
    created: Mapped[datetime] = mapped_column(insert_default=func.now())
    retired: Mapped[datetime] = mapped_column(nullable=True)
