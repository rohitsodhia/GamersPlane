from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import User, UserMeta


class UserRepository:
    def __init__(self, db_session: AsyncSession):
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

    async def get_user_by_id(
        self, id: int, include_meta: bool = False
    ) -> User | None:
        statement = (
            select(User).where(User.id == id, User.activated_on.is_not(None)).limit(1)
        )
        if include_meta:
            statement = statement.options(joinedload(User.meta))
        return await self.db_session.scalar(statement)

    async def get_user_by_username(self, username: str) -> User | None:
        return await self.db_session.scalar(
            select(User)
            .where(
                func.lower(User.username) == username.lower(),
                User.activated_on.is_not(None),
            )
            .limit(1)
        )

    async def get_user_by_identifier(self, identifier: str) -> User | None:
        return await self.db_session.scalar(
            select(User)
            .where(
                or_(
                    func.lower(User.username) == identifier,
                    func.lower(User.email) == identifier,
                ),
                User.activated_on.is_not(None),
            )
            .limit(1)
        )

    async def update_user_meta(
        self, user: User, updates: dict[UserMeta.MetaKeys, str | bool | date | None]
    ) -> None:
        meta_by_key = {meta.key: meta for meta in user.meta}
        for key, value in updates.items():
            stored_value = value.isoformat() if isinstance(value, date) else value
            existing_user_meta = meta_by_key.get(key.value)
            if existing_user_meta:
                existing_user_meta.value = stored_value
            else:
                user.meta.append(
                    UserMeta(user_id=user.id, key=key.value, value=stored_value)
                )

        self.db_session.add(user)
        await self.db_session.flush()

    async def delete_user_meta(self, user: User, key: UserMeta.MetaKeys) -> None:
        existing_user_meta = next(
            (meta for meta in user.meta if meta.key == key.value), None
        )
        if existing_user_meta:
            user.meta.remove(existing_user_meta)
            await self.db_session.delete(existing_user_meta)
            await self.db_session.flush()

    async def update_last_activity(self, user: User) -> None:
        now = datetime.now(timezone.utc)
        if user.last_activity and now - user.last_activity < timedelta(minutes=5):
            return
        user.last_activity = now
        self.db_session.add(user)
        await self.db_session.flush()
