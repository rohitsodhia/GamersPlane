from sqlalchemy import and_, case, func, literal, select, text
from sqlalchemy.orm import aliased, joinedload

from app.database import DBSessionDependency
from app.models.legacy import User, UserMeta
from app.users.functions import get_avatar_path


class UserRepository:
    def __init__(
        self,
        db_session: DBSessionDependency,
        authed_user: User | None = None,
    ):
        self.db_session = db_session
        self.authed_user = authed_user

    async def get_user(self, user_id: int, include_meta: bool = False) -> User | None:
        query = select(User).where(User.id == user_id).limit(1)
        if include_meta:
            query = query.options(joinedload(User.meta))
        user = await self.db_session.scalar(query)
        return user

    async def get_avatar(self, user_id: int):
        avatar_ext = await self.db_session.scalar(
            select(UserMeta._value)
            .where(
                and_(
                    UserMeta.user_id == user_id,
                    UserMeta.key == UserMeta.MetaKeys.AVATAR_EXT.value,
                )
            )
            .limit(1)
        )

        return get_avatar_path(user_id, avatar_ext)

    async def get_gamers(
        self,
        get_inactive: bool = False,
        get_lfg: bool = False,
    ):
        fifteen_min_ago = func.date_sub(func.now(), text("INTERVAL 15 MINUTE"))
        two_weeks_ago = func.date_sub(func.now(), text("INTERVAL 2 WEEK"))

        online_expr = case(
            (User.last_activity >= fifteen_min_ago, literal(1)), else_=literal(0)
        ).label("online")

        UserMetaAvatar = aliased(UserMeta)
        UserMetaLFG = aliased(UserMeta)

        statement = (
            select(
                User.id,
                User.username,
                User.last_activity,
                online_expr,
                UserMetaAvatar._value.label("avatar_ext"),
                UserMetaLFG._value.label("lfg"),
            )
            .outerjoin(
                UserMetaAvatar,
                (User.id == UserMetaAvatar.user_id)
                & (UserMetaAvatar.key == UserMetaAvatar.MetaKeys.AVATAR_EXT.value),
            )
            .outerjoin(
                UserMetaLFG,
                (User.id == UserMetaLFG.user_id)
                & (UserMetaLFG.key == UserMetaLFG.MetaKeys.LOOKING_FOR_A_GAME.value),
            )
            .where(User.activated_on.is_not(None), User.last_activity.is_not(None))
            .order_by(online_expr.desc(), User.username)
        )

        if not get_inactive:
            statement = statement.where(User.last_activity >= two_weeks_ago)

        return await self.db_session.execute(statement)
