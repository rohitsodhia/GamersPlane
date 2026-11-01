from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.configs import configs
from app.models import Role, System, User, UserLFGSystem, UserMeta, UserRole

GamerSort = Literal["name", "newest", "oldest"]
GAMERS_PER_PAGE = 25
# No activity for this long and a gamer counts as inactive.
GAMER_INACTIVE_AFTER = timedelta(days=14)


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

    async def get_role_members(self, role_id: int) -> Sequence[User]:
        """Active, unbanned users explicitly in the role, by username (A-Z, any
        case). A soft-deleted role has no members (its join is filtered out)."""
        return (
            await self.db_session.scalars(
                select(User)
                .join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .where(
                    Role.id == role_id,
                    User.activated_on.is_not(None),
                    User.banned.is_(None),
                )
                .order_by(func.lower(User.username), User.id)
            )
        ).all()

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

    @staticmethod
    def _gamer_filters(
        *, search: str | None, lfg: bool, include_inactive: bool, now: datetime
    ):
        filters = [
            User.activated_on.is_not(None),
            User.banned.is_(None),
            or_(User.suspended_until.is_(None), User.suspended_until <= now),
        ]
        if search:
            escaped = (
                search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            filters.append(User.username.ilike(f"%{escaped}%", escape="\\"))
        if lfg:
            filters.append(
                exists().where(
                    UserMeta.user_id == User.id,
                    UserMeta.key == UserMeta.MetaKeys.LOOKING_FOR_A_GAME.value,
                    UserMeta._value == "1",
                )
            )
        if not include_inactive:
            # A null last_activity compares as NULL (falsey), so it's excluded too.
            filters.append(User.last_activity >= now - GAMER_INACTIVE_AFTER)
        return filters

    async def get_gamers(
        self,
        *,
        search: str | None = None,
        lfg: bool = False,
        include_inactive: bool = False,
        sort: GamerSort = "name",
        page: int = 1,
        limit: int = GAMERS_PER_PAGE,
    ) -> Sequence[User]:
        filters = self._gamer_filters(
            search=search,
            lfg=lfg,
            include_inactive=include_inactive,
            now=datetime.now(timezone.utc),
        )
        order_by = {
            "name": (func.lower(User.username), User.id),
            "newest": (User.join_date.desc(), User.id.desc()),
            "oldest": (User.join_date, User.id),
        }[sort]
        statement = (
            select(User)
            .where(*filters)
            .order_by(*order_by)
            .limit(limit)
            .offset((page - 1) * limit)
            .options(selectinload(User.meta))
        )
        return (await self.db_session.scalars(statement)).all()

    async def count_gamers(
        self,
        *,
        search: str | None = None,
        lfg: bool = False,
        include_inactive: bool = False,
    ) -> int:
        filters = self._gamer_filters(
            search=search,
            lfg=lfg,
            include_inactive=include_inactive,
            now=datetime.now(timezone.utc),
        )
        return (
            await self.db_session.scalar(
                select(func.count()).select_from(User).where(*filters)
            )
        ) or 0

    async def get_lfg_systems(self, user_id: int) -> Sequence[System]:
        return (
            await self.db_session.scalars(
                select(System)
                .join(UserLFGSystem, UserLFGSystem.system_id == System.id)
                .where(UserLFGSystem.user_id == user_id)
                .order_by(System.sort_name, System.id)
            )
        ).all()

    async def get_new_game_mail_recipients(
        self, system_id: str, exclude_user_id: int
    ) -> list[str]:
        """Emails of active users looking for ``system_id`` who opted in to new
        game mail. A missing newGameMail row counts as opted out."""
        now = datetime.now(timezone.utc)
        return list(
            (
                await self.db_session.scalars(
                    select(User.email)
                    .join(UserLFGSystem, UserLFGSystem.user_id == User.id)
                    .where(
                        UserLFGSystem.system_id == system_id,
                        User.id != exclude_user_id,
                        User.activated_on.is_not(None),
                        User.banned.is_(None),
                        or_(
                            User.suspended_until.is_(None), User.suspended_until <= now
                        ),
                        exists().where(
                            UserMeta.user_id == User.id,
                            UserMeta.key == UserMeta.MetaKeys.NEW_GAME_MAIL.value,
                            UserMeta._value == "1",
                        ),
                    )
                    .order_by(User.id)
                )
            ).all()
        )

    async def set_lfg_systems(self, user_id: int, system_ids: Iterable[str]) -> None:
        """Replace the user's LFG systems with exactly ``system_ids``."""
        wanted = set(system_ids)
        current = set(
            (
                await self.db_session.scalars(
                    select(UserLFGSystem.system_id).where(
                        UserLFGSystem.user_id == user_id
                    )
                )
            ).all()
        )
        if current - wanted:
            await self.db_session.execute(
                delete(UserLFGSystem).where(
                    UserLFGSystem.user_id == user_id,
                    UserLFGSystem.system_id.in_(current - wanted),
                )
            )
        self.db_session.add_all(
            UserLFGSystem(user_id=user_id, system_id=system_id)
            for system_id in wanted - current
        )
        await self.db_session.flush()

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
