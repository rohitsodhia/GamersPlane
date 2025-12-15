from datetime import datetime
from typing import List

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column

from app.models.legacy.base import LegacyBase


class PM(MappedAsDataclass, AsyncAttrs, LegacyBase):
    __tablename__ = "pms"

    id: Mapped[int] = mapped_column("pmID", primary_key=True, init=False)
    recipient_id: Mapped[int] = mapped_column("recipientID", ForeignKey("users.userID"))
    sender_id: Mapped[int] = mapped_column("senderID", ForeignKey("users.userID"))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text())
    datestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now(), init=False
    )
    recipient_read: Mapped[bool] = mapped_column("recipientRead", default=False)
    sender_read: Mapped[bool] = mapped_column("senderRead", default=False)
    reply_to_id: Mapped[int | None] = mapped_column(
        "replyTo", ForeignKey("pms.pmID"), default=None
    )
    recipeint_deleted: Mapped[bool] = mapped_column("recipientDeleted", default=False)
    sender_deleted: Mapped[bool] = mapped_column("senderDeleted", default=False)
    history: Mapped[List[int]] = mapped_column(JSON(), default_factory=list)
