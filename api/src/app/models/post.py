from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates,
)

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models import Character, Thread, User


class Post(Base, SoftDeleteMixin, TimestampMixin):
    class States(LabelEnum):
        DRAFT = "d", "Draft"
        PUBLISHED = "p", "Published"
        REVISED = "r", "Revised"

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), index=True)
    thread: Mapped[Thread] = relationship(
        foreign_keys=[thread_id], back_populates="posts", lazy="joined"
    )
    title: Mapped[str]
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped[User] = relationship(lazy="joined")
    body: Mapped[dict] = mapped_column(JSON())
    state: Mapped[States] = mapped_column(
        LabelEnumType(States, String(1)), default=States.DRAFT
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revision_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id"), nullable=True
    )
    revision_of: Mapped[Post | None] = relationship()
    posted_as_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id"), nullable=True
    )
    posted_as: Mapped[Character | None] = relationship(lazy="joined")

    @validates("state")
    def _validate_state(self, key: str, state: States) -> States:
        if state == self.States.PUBLISHED and self.published_at is None:
            self.published_at = datetime.now(UTC)
        return state
