from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models import User


class PM(Base, TimestampMixin):
    __tablename__ = "pms"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recipient: Mapped["User"] = relationship(foreign_keys=[recipient_id])
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text())
    datestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )
    recipient_read: Mapped[bool] = mapped_column(default=False)
    sender_read: Mapped[bool] = mapped_column(default=False)
    reply_to_id: Mapped[int | None] = mapped_column(ForeignKey("pms.id"), default=None)
    recipient_deleted: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    sender_deleted: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    history_ids: Mapped[List[int]] = mapped_column(JSON(), default=list)
