from __future__ import annotations

from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.database import DBSessionDependency
from app.models.legacy import PM, User

Box = Literal["inbox", "outbox"]


class NoRecipientException(Exception):
    def __init__(self):
        super().__init__("No recipient found")


class PMSelfException(Exception):
    def __init__(self):
        super().__init__("Attepting to PM self")


class PMRepository:
    def __init__(
        self,
        db_session: DBSessionDependency,
        authed_user: User,
    ):
        self.db_session = db_session
        self.authed_user = authed_user

    async def get_pm_count(self, user_id: int, box: Box = "inbox") -> int | None:
        pass

    def __filter_by_box(self, box: Box, user_id: int):
        if box == "inbox":
            return PM.recipient_id == user_id
        else:
            return PM.sender_id == user_id

    async def get_pms(
        self,
        user_id: int,
        *,
        page: int,
        limit: int,
        sort: Literal["asc", "desc"] = "desc",
        box: Literal["inbox", "outbox"] = "inbox",
    ):
        statement = (
            select(PM)
            .where(self.__filter_by_box(box, user_id))
            .limit(limit)
            .offset((page - 1) * limit)
            .order_by(PM.datestamp.desc() if sort == "desc" else PM.datestamp.asc())
            .options(joinedload(PM.recipient), joinedload(PM.sender))
        )

        pms = await self.db_session.scalars(statement)

        return pms

    async def count_pms(self, user_id: int, box: Box = "inbox"):
        return await self.db_session.scalar(
            select(func.count(PM.id)).where(self.__filter_by_box(box, user_id))
        )

    async def send_pm(
        self,
        title: str,
        message: str,
        reply_to_id: int | None = None,
        recipient_id: int | None = None,
        recipient_username: str | None = None,
    ) -> PM:
        recipient = await self.db_session.scalar(
            select(User).where(User.username == recipient_username).limit(1)
        )
        if not recipient:
            raise NoRecipientException()
        if recipient.id == self.authed_user.id:
            raise PMSelfException()

        pm = PM(
            recipient_id=recipient.id,
            sender_id=self.authed_user.id,
            title=title,
            message=message,
        )
        if reply_to_id:
            reply_pm = await self.db_session.scalar(
                select(PM).where(PM.id == reply_to_id).limit(1)
            )

            if reply_pm:
                pm.reply_to_id = reply_to_id
                pm.history = reply_pm.history.copy()
                pm.history.append(self.authed_user.id)
        self.db_session.add(pm)
        await self.db_session.commit()
        return pm
