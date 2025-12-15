from __future__ import annotations

from typing import Literal

from sqlalchemy import select

from app.models.legacy import PM, User


class NoRecipientException(Exception):
    def __init__(self):
        super().__init__("No recipient found")


class PMSelfException(Exception):
    def __init__(self):
        super().__init__("Attepting to PM self")


class PMRepository:
    def __init__(
        self,
        db_session,
        authed_user: User,
    ):
        self.db_session = db_session
        self.authed_user = authed_user

    async def get_pm_count(
        self, user_id: int, box: Literal["inbox", "outbox"] = "inbox"
    ) -> int | None:
        pass

    async def get_pms(
        self, user_id: int, box: Literal["inbox", "outbox"] = "inbox", page: int = 1
    ) -> int | None:
        if page < 1:
            page = 1

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
            pm.reply_to_id = reply_to_id
            pm.history = reply_pm.history.copy()
            pm.history.append(self.authed_user.id)
        self.db_session.add(pm)
        await self.db_session.commit()
        return pm
