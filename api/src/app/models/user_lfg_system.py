from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserLFGSystem(Base):
    """A site system a user wants new-game notifications for."""

    __tablename__ = "user_lfg_systems"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    system_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("systems.id"), primary_key=True, index=True
    )
