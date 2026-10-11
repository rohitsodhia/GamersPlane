from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.game_image import GameImage


class GameNPC(Base, TimestampMixin):
    """A quick NPC: a name + optional library image a GM can post as.

    Deliberately does not use ``SoftDeleteMixin``. The mixin's global SELECT
    filter would also hide a deleted NPC when it is loaded through
    ``Post.posted_npc``, and old posts must keep rendering it. Queries that
    list, suggest or look up NPCs filter ``deleted IS NULL`` themselves.
    """

    __tablename__ = "game_npcs"
    __table_args__ = (
        # One live pair per (game, name, image); a missing image counts as equal.
        Index(
            "uq_game_npcs_game_id_name_image_id",
            "game_id",
            "name",
            "image_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("deleted IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    image_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "game_images.id", ondelete="SET NULL", name="game_npcs_image_id_fkey"
        ),
        nullable=True,
    )
    image: Mapped[GameImage | None] = relationship(lazy="joined")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
