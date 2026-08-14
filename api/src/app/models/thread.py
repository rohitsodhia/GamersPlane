from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.types import ClassWrappedJSON

if TYPE_CHECKING:
    from app.models import Forum, Post


class Thread(Base, SoftDeleteMixin, TimestampMixin):
    class Options(BaseModel):
        model_config = ConfigDict(extra="forbid")

        sticky: bool = False
        locked: bool = False
        allow_public_posting: bool = False
        allow_rolls: bool = False
        allow_draws: bool = False
        discord_webhook: str | None = None

    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(primary_key=True)
    forum_id: Mapped[int] = mapped_column(ForeignKey("forums.id"), index=True)
    forum: Mapped[Forum] = relationship(lazy="joined")
    options: Mapped[Options] = mapped_column(
        ClassWrappedJSON(Options), default=Options
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
