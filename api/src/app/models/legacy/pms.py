from typing import List

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column

from app.models.legacy.base import LegacyBase


class PMs(MappedAsDataclass, AsyncAttrs, LegacyBase):
    __tablename__ = "pms"

    id: Mapped[int] = mapped_column("pmID", primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text())
    recipient_read: Mapped[bool] = mapped_column(default=False)
    sender_read: Mapped[bool] = mapped_column(default=False)
    reply_to_id: Mapped[int | None] = mapped_column(ForeignKey("pms.id"), default=None)
    recipeint_deleted: Mapped[bool] = mapped_column(default=False)
    sender_deleted: Mapped[bool] = mapped_column(default=False)
    history: Mapped[List[int]] = mapped_column(JSON(), default_factory=list)
