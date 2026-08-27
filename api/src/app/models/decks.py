from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models import Game, User


class DeckType(Base):
    __tablename__ = "deck_types"

    short: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str]
    deck_size: Mapped[int]


class Deck(Base, TimestampMixin):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    game: Mapped[Game] = relationship()
    type_id: Mapped[str] = mapped_column(String(10), ForeignKey("deck_types.short"))
    label: Mapped[str]
    type: Mapped[DeckType] = relationship(lazy="joined")
    order: Mapped[list[int]] = mapped_column(JSON())
    position: Mapped[int]
    last_shuffled: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    permissions: Mapped[list[DeckPermission]] = relationship(
        back_populates="deck", cascade="all, delete-orphan"
    )


class DeckPermission(Base):
    __tablename__ = "deck_permissions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    user: Mapped[User] = relationship()
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id"), primary_key=True)
    deck: Mapped[Deck] = relationship(back_populates="permissions")
