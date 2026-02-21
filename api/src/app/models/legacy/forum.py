from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, types
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.legacy.base import LegacyBase

if TYPE_CHECKING:
    from app.models.legacy import Forum, Game


class ForumTypeDecorator(types.TypeDecorator):
    impl = types.String(1)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value.value if isinstance(value, Enum) else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Forum.ForumTypes(value)


class Forum(LegacyBase):
    class ForumTypes(Enum):
        FORUM = "f"
        CATEGORY = "c"

    __tablename__ = "forums"

    id: Mapped[int] = mapped_column("forumID", primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text(), nullable=True)
    forum_type: Mapped[ForumTypes] = mapped_column(
        "forumType",
        ForumTypeDecorator,
        default=ForumTypes.FORUM.value,
        nullable=True,
    )
    parent_id: Mapped[int] = mapped_column(
        "parentID", ForeignKey("forums.forumID"), nullable=True
    )
    parent: Mapped["Forum"] = relationship(
        "Forum", back_populates="children", remote_side="Forum.id"
    )
    children: Mapped[list["Forum"]] = relationship(back_populates="parent")
    depth: Mapped[int] = mapped_column(nullable=True)
    order: Mapped[int]
    game_id: Mapped[int | None] = mapped_column(
        "gameID", ForeignKey("games.gameID"), nullable=True
    )
    game: Mapped["Game"] = relationship(
        "Game",
        primaryjoin="Forum.game_id == Game.id",
        foreign_keys=[game_id],
        post_update=True,
    )
    thread_count: Mapped[int] = mapped_column("threadCount", default=0)
