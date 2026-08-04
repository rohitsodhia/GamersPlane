from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.configs import configs
from app.exceptions import ForbiddenException, NotFoundException
from app.models import PM, User

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
        db_session: AsyncSession,
        authed_user: User,
    ):
        self.db_session = db_session
        self.authed_user = authed_user

    def __filter_by_box(self, box: Box, user_id: int):
        if box == "inbox":
            return PM.recipient_id == user_id, PM.recipient_deleted.is_(None)
        else:
            return PM.sender_id == user_id, PM.sender_deleted.is_(None)

    async def get_pms(
        self,
        user_id: int,
        *,
        page: int = 1,
        limit: int = configs.PAGINATE_PER_PAGE,
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

    async def count_pms(
        self,
        user_id: int,
        box: Box = "inbox",
        state: Literal["all", "read", "unread"] = "all",
    ):
        statement = select(func.count(PM.id)).where(*self.__filter_by_box(box, user_id))
        if state == "read":
            statement = statement.where(PM.recipient_read)
        elif state == "unread":
            statement = statement.where(~PM.recipient_read)
        return await self.db_session.scalar(statement)

    async def get_pm(self, pm_id: int):
        pm = await self.db_session.scalar(
            select(PM)
            .where(
                PM.id == pm_id,
                or_(
                    and_(
                        PM.recipient_id == self.authed_user.id,
                        PM.recipient_deleted.is_(None),
                    ),
                    and_(
                        PM.sender_id == self.authed_user.id,
                        PM.sender_deleted.is_(None),
                    ),
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

    async def get_pm_history(self, pm: PM) -> list[PM]:
        pms = await self.db_session.scalars(
            select(PM)
            .where(PM.id.in_(pm.history_ids))
            .order_by(PM.datestamp.desc())
            .options(joinedload(PM.recipient), joinedload(PM.sender))
        )
        history: list[PM] = []
        for pm in pms:
            if (
                pm.recipient.id == self.authed_user.id
                or pm.sender.id == self.authed_user.id
            ):
                history.append(pm)

        return history

    async def send_pm(
        self,
        title: str,
        message: dict,
        reply_to_id: int | None = None,
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
            reply_pm = (
                await self.db_session.execute(
                    select(
                        PM.id,
                        PM.recipient_id,
                        PM.sender_id,
                        PM.recipient_deleted,
                        PM.sender_deleted,
                        PM.history_ids,
                    )
                    .where(
                        PM.id == reply_to_id,
                        or_(
                            and_(
                                PM.recipient_id == self.authed_user.id,
                                PM.recipient_deleted.is_(None),
                            ),
                            and_(
                                PM.sender_id == self.authed_user.id,
                                PM.sender_deleted.is_(None),
                            ),
                        ),
                    )
                    .limit(1)
                )
            ).first()
            if reply_pm:
                pm.reply_to_id = reply_to_id
                pm.history_ids = [reply_pm.id] + reply_pm.history_ids
        self.db_session.add(pm)
        await self.db_session.flush()
        return pm

    async def delete_pm(self, pm_id: int):
        pm = await self.get_pm(pm_id)
        if not pm:
            raise NotFoundException()
        elif self.authed_user.id == pm.recipient.id:
            pm.recipient_deleted = datetime.now(timezone.utc)
        elif self.authed_user.id == pm.sender.id:
            pm.sender_deleted = datetime.now(timezone.utc)
        else:
            raise ForbiddenException()
        await self.db_session.flush()
