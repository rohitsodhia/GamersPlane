from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.enums import LabelEnum, LabelEnumArrayType
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models import Forum, Post


class Thread(Base, SoftDeleteMixin, TimestampMixin):
    class ThreadOptions(LabelEnum):
        STICKY = "sticky", "Sticky"
        LOCKED = "locked", "Locked"
        ALLOW_ROLLS = "allowRolls", "Allow Rolls"
        ALLOW_DRAWS = "allowDraws", "Allow Draws"

    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(primary_key=True)
    forum_id: Mapped[int] = mapped_column(ForeignKey("forums.id"), index=True)
    forum: Mapped[Forum] = relationship(lazy="joined")
    options: Mapped[list[ThreadOptions]] = mapped_column(
        LabelEnumArrayType(ThreadOptions, String()), default=list
    )
    first_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id"), nullable=True
    )
    first_post: Mapped[Post | None] = relationship(
        foreign_keys=[first_post_id], lazy="selectin"
    )
    last_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id"), nullable=True
    )
    last_post: Mapped[Post | None] = relationship(
        foreign_keys=[last_post_id], lazy="selectin"
    )
    post_count: Mapped[int] = mapped_column(default=0)
    posts: Mapped[list[Post]] = relationship(
        foreign_keys="Post.thread_id", back_populates="thread"
    )
