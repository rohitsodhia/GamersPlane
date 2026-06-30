from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import User


class UserRepository:
    def __init__(self, db_session):
        self.db_session = db_session

    async def get_user(self, user_id: int) -> User | None:
        user = await self.db_session.scalar(
            select(User)
            .where(User.id == user_id)
            .limit(1)
            .options(joinedload(User.meta))
        )
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        user = await self.db_session.scalar(
            select(User).where(User.email == email).limit(1)
        )
        return user
