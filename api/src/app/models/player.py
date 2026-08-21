from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class Player(Base, TimestampMixin):
    __tablename__ = "players"

    class States(LabelEnum):
        APPLIED = "applied", "Applied"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        REMOVED = "removed", "Removed"
        LEFT = "left", "Left"

    game_id: Mapped[int] = mapped_column(
        "gameID", ForeignKey("games.id"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        "userID", ForeignKey("users.id"), primary_key=True
    )
    state: Mapped[States] = mapped_column(
        LabelEnumType(States, String(8)), default=States.APPLIED
    )
    is_gm: Mapped[bool] = mapped_column(default=False)
