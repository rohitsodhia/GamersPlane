from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ForumRead(Base):
    """Everything in the forum (and below it) published up to ``read_until`` is
    read by ``user_id``."""

    __tablename__ = "forum_reads"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    forum_id: Mapped[int] = mapped_column(ForeignKey("forums.id"), primary_key=True)
    read_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
