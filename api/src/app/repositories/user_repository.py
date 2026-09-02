from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.configs import configs
from app.models import Role, User, UserMeta


class UserRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_user(self, user_id: int) -> User | None:
        user = await self.db_session.scalar(
            select(User)
            .where(User.id == user_id)
            .limit(1)
            .options(
                joinedload(User.meta),
                selectinload(User.roles).selectinload(Role.grants),
            )
        )
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        user = await self.db_session.scalar(
            select(User).where(User.email == email).limit(1)
        )
        return user

    async def get_user_by_id(self, id: int, include_meta: bool = False) -> User | None:
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

    async def search_users_by_username_prefix(
        self, prefix: str, limit: int = 10
    ) -> Sequence[User]:
        return (
            await self.db_session.scalars(
                select(User)
                .where(
                    func.lower(User.username).startswith(prefix.lower()),
                    User.activated_on.is_not(None),
                )
                .order_by(func.lower(User.username))
                .limit(limit)
            )
        ).all()

    @staticmethod
    def _list_users_filters(prefix: str | None, banned: bool | None):
        # Unlike search/autocomplete this deliberately includes unactivated
        # accounts: the user-management screen needs them to resend activation.
        filters = []
        if prefix:
            filters.append(func.lower(User.username).startswith(prefix.lower()))
        if banned is True:
            filters.append(User.banned.is_not(None))
        elif banned is False:
            filters.append(User.banned.is_(None))
        return filters

    async def get_users(
        self,
        *,
        prefix: str | None = None,
        banned: bool | None = None,
        page: int = 1,
        limit: int = configs.PAGINATE_PER_PAGE,
    ) -> Sequence[User]:
        # meta is always eager-loaded: User.avatar reads it even for lightweight rows.
        statement = (
            select(User)
            .where(*self._list_users_filters(prefix, banned))
            .order_by(User.join_date, User.id)
            .limit(limit)
            .offset((page - 1) * limit)
            .options(selectinload(User.meta))
        )
        return (await self.db_session.scalars(statement)).all()

    async def count_users(
        self, *, prefix: str | None = None, banned: bool | None = None
    ) -> int:
        return (
            await self.db_session.scalar(
                select(func.count())
                .select_from(User)
                .where(*self._list_users_filters(prefix, banned))
            )
        ) or 0

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

    async def toggle_ban(self, user: User) -> datetime | None:
        """Flip a user's ban state: unbanned -> banned now, banned -> unbanned."""
        user.banned = None if user.banned else datetime.now(timezone.utc)
        self.db_session.add(user)
        await self.db_session.flush()
        return user.banned

    async def update_last_activity(self, user: User) -> None:
        now = datetime.now(timezone.utc)
        if user.last_activity and now - user.last_activity < timedelta(minutes=5):
            return
        user.last_activity = now
        self.db_session.add(user)
        await self.db_session.flush()
