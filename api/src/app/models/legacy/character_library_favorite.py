from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.legacy.base import LegacyBase


class CharacterLibraryFavorite(LegacyBase):
    __tablename__ = "characterLibrary_favorites"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.userID"), primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.characterID"), primary_key=True
    )
