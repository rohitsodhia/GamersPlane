import datetime
from enum import Enum
from typing import TYPE_CHECKING, List

from models.base import Base, SoftDeleteMixin, TimestampMixin
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from models import Forum, ForumGroup, System, User


class Game(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "games"

    class Statuses(Enum):
        OPEN = True, "Open"
        CLOSED = False, "Closed"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50))
    system_id: Mapped[int] = mapped_column(ForeignKey("publishers.id"))
    system: Mapped["System"] = relationship()
    allowed_char_sheets: Mapped[List["System"]] = relationship(
        secondary="game_allowed_systems"
    )
    gm_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    gm: Mapped["User"] = relationship()
    created: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )
    start: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )
    end: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    post_frequency: Mapped[str] = mapped_column(String(4))
    num_players: Mapped[int] = mapped_column()
    chars_per_player: Mapped[int] = mapped_column(default=1)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    char_gen_info: Mapped[str | None] = mapped_column(Text(), nullable=True)
    root_forum_id: Mapped[int] = mapped_column(ForeignKey("forums.id"))
    root_forum: Mapped["Forum"] = relationship()
    group_id: Mapped[int] = mapped_column(ForeignKey("forum_groups.id"))
    group: Mapped["ForumGroup"] = relationship()
    status: Mapped[Statuses] = mapped_column(default=Statuses.OPEN)
    public: Mapped[bool] = mapped_column()
    retired: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
