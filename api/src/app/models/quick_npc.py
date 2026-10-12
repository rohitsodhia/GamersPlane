from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.npc_image import NPCImage


class QuickNPC(Base, TimestampMixin):
    """A quick NPC: a name + optional library image to post as. Owned by a game
    (any of its accepted players can use it) or by a user (their personal NPCs).

    Deliberately does not use ``SoftDeleteMixin``. The mixin's global SELECT
    filter would also hide a deleted NPC when it is loaded through
    ``Post.posted_npc``, and old posts must keep rendering it. Queries that
    list, suggest or look up NPCs filter ``deleted IS NULL`` themselves.
    """

    __tablename__ = "quick_npcs"
    __table_args__ = (
        CheckConstraint(
            "(game_id IS NULL) <> (user_id IS NULL)",
            name="ck_quick_npcs_one_owner",
        ),
        # One live pair per (owner, name, image); a missing image counts as equal.
        Index(
            "uq_quick_npcs_owner_name_image_id",
            "game_id",
            "user_id",
            "name",
            "image_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("deleted IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int | None] = mapped_column(
        ForeignKey("games.id"), index=True, nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(100))
    image_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "npc_images.id", ondelete="SET NULL", name="quick_npcs_image_id_fkey"
        ),
        nullable=True,
    )
    image: Mapped[NPCImage | None] = relationship(lazy="joined")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
