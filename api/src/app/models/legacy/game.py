import datetime
from enum import Enum
from typing import TYPE_CHECKING, Literal, TypedDict

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func, types
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.sqlalchemy_types import EnumValueDecorator
from app.models.legacy.base import LegacyBase

if TYPE_CHECKING:
    from app.models.legacy import Forum, ForumGroup, System, User


class Game(LegacyBase):
    __tablename__ = "games"

    class Statuses(Enum):
        OPEN = True
        CLOSED = False

    class PostFrequency(TypedDict):
        timesPer: int
        perPeriod: Literal["d", "w"]

    id: Mapped[int] = mapped_column("gameID", primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    system_id: Mapped[int] = mapped_column("system", ForeignKey("systems.id"))
    system: Mapped["System"] = relationship()
    custom_system: Mapped[str] = mapped_column("customSystem", nullable=True)
    gm_id: Mapped[int] = mapped_column("gmID", ForeignKey("users.userID"))
    gm: Mapped["User"] = relationship(foreign_keys=[gm_id])
    created: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )
    start: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )
    end: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    post_frequency: Mapped[PostFrequency] = mapped_column("postFrequency", JSON())
    num_players: Mapped[int] = mapped_column("numPlayers")
    chars_per_player: Mapped[int] = mapped_column("charsPerPlayer", default=1)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    char_gen_info: Mapped[str | None] = mapped_column(
        "charGenInfo", Text(), nullable=True
    )
    root_forum_id: Mapped[int] = mapped_column("forumID", ForeignKey("forums.forumID"))
    root_forum: Mapped["Forum"] = relationship(
        "Forum",
        primaryjoin="Game.root_forum_id == Forum.id",
        foreign_keys=[root_forum_id],
        uselist=False,
    )
    group_id: Mapped[int] = mapped_column(
        "groupID", ForeignKey("forums_groups.groupID")
    )
    group: Mapped["ForumGroup"] = relationship(foreign_keys=[group_id])
    status: Mapped[Statuses] = mapped_column(
        EnumValueDecorator(enum_class=Statuses, impl_class=types.String(1)),
        default=Statuses.OPEN,
    )
    public: Mapped[bool]
    retired: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    allowed_char_sheets: Mapped[list[str]] = mapped_column("allowedCharSheets", JSON())
    game_options: Mapped[dict] = mapped_column("gameOptions", JSON())
    recruitment_thread_id: Mapped[int] = mapped_column("recruitmentThreadId")
