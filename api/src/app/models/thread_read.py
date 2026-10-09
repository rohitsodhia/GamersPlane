from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ThreadRead(Base):
    """How far ``user_id`` has read a thread, by post ``published_at``.

    ``read_until`` is null when nothing is read. A ``pinned`` row (the user marked
    the thread unread) ignores the forum-level read marker.
    """

    __tablename__ = "thread_reads"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), primary_key=True)
    read_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pinned: Mapped[bool] = mapped_column(default=False, server_default=false())
