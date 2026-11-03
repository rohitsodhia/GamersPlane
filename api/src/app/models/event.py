from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base


class Event(Base):
    """Something that happened that other users are told about, with a recipient
    row for each user told. Which columns are set depends on the type:

    - ``mention``: one event per post (``post_id``, ``thread_id``), recipients are
      the users the post mentions (see ``sync_post_mentions``).
    - ``game_invite``: one per invited user per game (``game_id``,
      ``subject_user_id`` is the invitee), the invitee is the recipient.
    - ``game_application``: one per applicant per game (``game_id``,
      ``subject_user_id`` is the applicant), the game's GMs are the recipients.
    - ``character_submitted``: one per character (``game_id``, ``character_id``),
      the game's GMs are the recipients.

    Nothing is deleted when the thing resolves; the notifications list checks the
    live state. Invites, applications, and submissions that happen again reuse the
    event (see ``EventRepository.upsert_event``).
    """

    class Types(LabelEnum):
        MENTION = "mention", "Mention"
        GAME_INVITE = "game_invite", "Game invite"
        GAME_APPLICATION = "game_application", "Game application"
        CHARACTER_SUBMITTED = "character_submitted", "Character submitted"

    __tablename__ = "events"
    __table_args__ = (
        # The mention one is also the index for finding a post's event.
        Index(
            "uq_events_mention_post",
            "post_id",
            unique=True,
            postgresql_where=text("type = 'mention'"),
        ),
        Index(
            "uq_events_game_subject",
            "type",
            "game_id",
            "subject_user_id",
            unique=True,
            postgresql_where=text("type IN ('game_invite', 'game_application')"),
        ),
        Index(
            "uq_events_character",
            "character_id",
            unique=True,
            postgresql_where=text("type = 'character_submitted'"),
        ),
        CheckConstraint(
            "(type = 'mention' AND post_id IS NOT NULL AND thread_id IS NOT NULL)"
            " OR (type IN ('game_invite', 'game_application')"
            " AND game_id IS NOT NULL AND subject_user_id IS NOT NULL)"
            " OR (type = 'character_submitted'"
            " AND game_id IS NOT NULL AND character_id IS NOT NULL)",
            name="ck_events_type_columns",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[Types] = mapped_column(LabelEnumType(Types, String(20)))
    # Who caused it: a mention's post author (even when a moderator's edit is what
    # added the mention), the inviting GM, the applicant, or the character's owner.
    # A reused event takes the latest actor.
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"), nullable=True)
    thread_id: Mapped[int | None] = mapped_column(
        ForeignKey("threads.id"), nullable=True
    )
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), nullable=True)
    subject_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    character_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id"), nullable=True
    )
    # Moves forward when a reused event is raised again.
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
