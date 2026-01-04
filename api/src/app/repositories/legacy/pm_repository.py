from __future__ import annotations

from typing import Literal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import joinedload

from app.database import DBSessionDependency
from app.exceptions import ForbiddenException, NotFoundException
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

    def __filter_by_box(self, box: Box, user_id: int):
        if box == "inbox":
            return PM.recipient_id == user_id, ~PM.recipient_deleted
        else:
            return PM.sender_id == user_id, ~PM.sender_deleted

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
            .where(*self.__filter_by_box(box, user_id))
            .limit(limit)
            .offset((page - 1) * limit)
            .order_by(PM.datestamp.desc() if sort == "desc" else PM.datestamp.asc())
            .options(joinedload(PM.recipient), joinedload(PM.sender))
        )

        pms = await self.db_session.scalars(statement)

        return pms

    async def count_pms(self, user_id: int, box: Box = "inbox"):
        return await self.db_session.scalar(
            select(func.count(PM.id)).where(*self.__filter_by_box(box, user_id))
        )

    async def get_pm(self, pm_id: int):
        pm = await self.db_session.scalar(
            select(PM)
            .where(
                PM.id == pm_id,
                or_(
                    and_(PM.recipient_id == self.authed_user.id, ~PM.recipient_deleted),
                    and_(PM.sender_id == self.authed_user.id, ~PM.sender_deleted),
                ),
            )
            .options(joinedload(PM.recipient), joinedload(PM.sender))
        )
        if not pm:
            raise NotFoundException()
        elif (
            self.authed_user.id != pm.recipient.id
            and self.authed_user.id != pm.sender.id
        ):
            raise ForbiddenException()

        return pm

    async def get_pm_history(self, pm: PM):
        history = list(
            await self.db_session.scalars(
                select(PM)
                .where(PM.id.in_(pm.history_ids))
                .order_by(PM.datestamp.desc())
                .options(joinedload(PM.recipient), joinedload(PM.sender))
            )
        )

        return history

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
                select(func.count(PM.id)).where(PM.id == reply_to_id).limit(1)
            )

            if reply_pm:
                pm.reply_to_id = reply_to_id
        self.db_session.add(pm)
        await self.db_session.commit()
        return pm

    async def delete_pm(self, pm_id: int):
        pm = await self.get_pm(pm_id)
        if not pm:
            raise NotFoundException()
        elif self.authed_user.id == pm.recipient.id:
            pm.recipient_deleted = True
        elif self.authed_user.id == pm.sender.id:
            pm.sender_deleted = True
        else:
            raise ForbiddenException()
        await self.db_session.commit()
