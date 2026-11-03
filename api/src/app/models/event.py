from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base


class Event(Base):
    """Something that happened on a post that other users are told about. For now
    the only kind is a mention: one event per post, with a recipient row for each
    user the post mentions (see ``sync_post_mentions``)."""

    class Types(LabelEnum):
        MENTION = "mention", "Mention"

    __tablename__ = "events"
    __table_args__ = (
        # Also the index for finding a post's event.
        UniqueConstraint("post_id", "type", name="uq_events_post_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[Types] = mapped_column(LabelEnumType(Types, String(20)))
    # The post's author, even when a moderator's edit is what added the mention.
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )


class EventRecipient(Base):
    """One user an event was sent to; kept after being read, never purged."""

    __tablename__ = "event_recipients"
    __table_args__ = (
        Index("ix_event_recipients_user_id_read_at", "user_id", "read_at"),
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Dismissed rows are hidden from the user's notifications for good (and count
    # as read); the row stays so the user is never notified of the event again.
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
