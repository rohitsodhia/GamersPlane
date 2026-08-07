from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models import Forum, Game


class Forum(Base, SoftDeleteMixin, TimestampMixin):
    class ForumTypes(LabelEnum):
        FORUM = "f", "Forum"
        CATEGORY = "c", "Category"

    __tablename__ = "forums"
    __table_args__ = (
        Index("ix_forums_heritage", "heritage", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text(), nullable=True)
    forum_type: Mapped[ForumTypes] = mapped_column(
        LabelEnumType(ForumTypes, String(1)),
        default=ForumTypes.FORUM,
        nullable=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("forums.id"), index=True, nullable=True
    )
    parent: Mapped[Forum | None] = relationship()
    heritage: Mapped[list[int]] = mapped_column(ARRAY(Integer()))
    order: Mapped[int]
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), nullable=True)
    game: Mapped[Game] = relationship(foreign_keys=[game_id])
    thread_count: Mapped[int] = mapped_column(default=0)
