from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models import User


class Report(Base, TimestampMixin):
    """A user's report of some content, kept with a snapshot of what was reported
    (the content can be edited or deleted afterwards)."""

    class TargetTypes(LabelEnum):
        POST = "post", "Post"
        THREAD = "thread", "Thread"
        USER = "user", "User"
        USER_AVATAR = "user_avatar", "User avatar"
        CHARACTER = "character", "Character"
        CHARACTER_AVATAR = "character_avatar", "Character avatar"
        GAME = "game", "Game"
        GAME_BACKGROUND = "game_background", "Game background"
        NPC_IMAGE = "npc_image", "NPC image"

    class Reasons(LabelEnum):
        ILLEGAL_CONTENT = "illegal_content", "Illegal content"
        COPYRIGHT = "copyright", "Copyright"
        HARASSMENT = "harassment", "Harassment"
        SPAM = "spam", "Spam"
        GUIDELINES = "guidelines", "Guidelines violation"
        OTHER = "other", "Other"

    class Statuses(LabelEnum):
        OPEN = "open", "Open"
        ACTIONED = "actioned", "Actioned"
        DISMISSED = "dismissed", "Dismissed"

    __tablename__ = "reports"
    __table_args__ = (
        # One open report per reporter per target; resolving frees them to report
        # it again.
        Index(
            "uq_reports_open_per_reporter_target",
            "reporter_id",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("ix_reports_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id])
    target_type: Mapped[TargetTypes] = mapped_column(
        LabelEnumType(TargetTypes, String(20))
    )
    # No foreign key: it points at a different table per target type, and the
    # report must outlive its target. For game_background it's the game's id, for
    # user_avatar the user's.
    target_id: Mapped[int]
    reason: Mapped[Reasons] = mapped_column(LabelEnumType(Reasons, String(20)))
    details: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[Statuses] = mapped_column(
        LabelEnumType(Statuses, String(10)), default=Statuses.OPEN
    )
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    resolver: Mapped[User | None] = relationship(foreign_keys=[resolved_by])
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # What the target looked like when it was reported.
    snapshot: Mapped[dict] = mapped_column(JSON())
    # Where the quarantined copy of a reported image is, relative to
    # QUARANTINE_DIR; null for text targets or when the file was already gone.
    snapshot_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
