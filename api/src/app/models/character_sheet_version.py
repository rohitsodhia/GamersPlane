from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models import CharacterSheet


class CharacterSheetVersion(Base, TimestampMixin):
    """A revision of a character sheet's layout.

    A row with ``published_at`` NULL is the sheet's draft: the only mutable
    version, at most one per sheet, with no ``number`` yet. Publishing stamps
    ``published_at`` and assigns the next ``number``; from then on the row is
    immutable so characters pinned to it never see it change.

    Deliberately not soft-deletable: deleting a sheet must not remove the
    versions characters are pinned to.
    """

    __tablename__ = "character_sheet_versions"
    __table_args__ = (
        UniqueConstraint("character_sheet_id", "number"),
        Index(
            "uq_character_sheet_versions_draft",
            "character_sheet_id",
            unique=True,
            postgresql_where=text("published_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    character_sheet_id: Mapped[int] = mapped_column(
        ForeignKey("character_sheets.id"), index=True
    )
    character_sheet: Mapped[CharacterSheet] = relationship(back_populates="versions")
    number: Mapped[int | None] = mapped_column(nullable=True)
    schema_version: Mapped[int] = mapped_column()
    layout: Mapped[dict] = mapped_column(JSON(), default=dict, deferred=True)
    changelog: Mapped[str | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def is_draft(self) -> bool:
        return self.published_at is None
