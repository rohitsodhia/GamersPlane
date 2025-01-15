from __future__ import annotations

from models import User
from sqlalchemy import select


class UserRepository:
    def __init__(self, db_session):
        self.db_session = db_session

    async def get_user(self, user_id) -> User | None:
        user = await self.db_session.scalar(
            select(User).where(User.id == user_id).limit(1)
        )
        return user