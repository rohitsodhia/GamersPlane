from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Poll(Base, TimestampMixin):
    """A thread's poll; a thread has at most one.

    Polls, options and votes are hard-deleted: removing an option removes its
    votes, and removing the poll removes both.
    """

    __tablename__ = "polls"

    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), primary_key=True)
    question: Mapped[str] = mapped_column(String(200))
    options_per_user: Mapped[int] = mapped_column(SmallInteger, default=1)
    allow_revoting: Mapped[bool] = mapped_column(default=False)


class PollOption(Base):
    __tablename__ = "poll_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("polls.thread_id"), index=True)
    text: Mapped[str] = mapped_column(String(200))
    # Display order. Not unique, so a reorder never needs to juggle values.
    position: Mapped[int]


class PollVote(Base):
    __tablename__ = "poll_votes"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    option_id: Mapped[int] = mapped_column(
        ForeignKey("poll_options.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )
