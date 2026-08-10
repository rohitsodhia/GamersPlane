from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models import Character, Thread, User


class Post(Base, SoftDeleteMixin, TimestampMixin):
    class States(LabelEnum):
        DRAFT = "d", "Draft"
        POST = "p", "Post"
        REVISION = "r", "Revision"

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
    revision_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id"), nullable=True
    )
    revision_of: Mapped[Post | None] = relationship()
    posted_as_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id"), nullable=True
    )
    posted_as: Mapped[Character | None] = relationship(lazy="joined")
