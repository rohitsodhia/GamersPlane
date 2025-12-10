from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class PMs(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "pms"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text())
    recipient_read: Mapped[bool] = mapped_column(default=False)
    sender_read: Mapped[bool] = mapped_column(default=False)
    reply_to_id: Mapped[int | None] = mapped_column(ForeignKey("pms.id"))
    recipeint_deleted: Mapped[bool] = mapped_column(default=False)
    sender_deleted: Mapped[bool] = mapped_column(default=False)
    history: Mapped[list[int]] = mapped_column(JSON())
