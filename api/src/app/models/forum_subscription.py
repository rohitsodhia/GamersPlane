from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ForumSubscription(Base):
    """A user's subscription to either one forum or one thread (never both).

    A forum subscription covers the threads whose forum is exactly that forum;
    subforums need their own subscription.
    """

    __tablename__ = "forum_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "(forum_id IS NULL) <> (thread_id IS NULL)",
            name="ck_forum_subscriptions_forum_xor_thread",
        ),
        # Nulls are distinct in Postgres, so each of these only constrains the
        # rows that use that target.
        UniqueConstraint("user_id", "forum_id", name="uq_forum_subscriptions_forum"),
        UniqueConstraint("user_id", "thread_id", name="uq_forum_subscriptions_thread"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    forum_id: Mapped[int | None] = mapped_column(
        ForeignKey("forums.id", ondelete="CASCADE"), index=True, nullable=True
    )
    thread_id: Mapped[int | None] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), index=True, nullable=True
    )


class ForumSubscriptionNotice(Base):
    """When a "new content" subscriber was last emailed about a thread, so they
    aren't emailed again until they've read it (see ``SubscriptionNotifier``).

    ``notified_through`` is the ``published_at`` of the newest post that email
    covered. Read tracking is by ``published_at``, so "have they read it" means
    their read point has reached this moment; ``notified_at`` is the wall-clock
    send time, kept for reference.
    """

    __tablename__ = "forum_subscription_notices"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), primary_key=True
    )
    notified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notified_through: Mapped[datetime] = mapped_column(DateTime(timezone=True))
