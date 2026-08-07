import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models import Forum, Role, System, User


class Game(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "games"

    class Statuses(LabelEnum):
        OPEN = True, "Open"
        CLOSED = False, "Closed"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50))
    system_id: Mapped[str] = mapped_column(ForeignKey("systems.id"))
    system: Mapped[System] = relationship()
    allowed_char_sheets: Mapped[list[System]] = relationship(
        secondary="game_allowed_systems"
    )
    gm_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    gm: Mapped[User] = relationship()
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
    root_forum: Mapped[Forum] = relationship(foreign_keys=[root_forum_id])
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    role: Mapped[Role] = relationship()
    status: Mapped[Statuses] = mapped_column(
        LabelEnumType(Statuses, Boolean), default=Statuses.OPEN
    )
    public: Mapped[bool] = mapped_column()
    retired: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
