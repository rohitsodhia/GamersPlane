from sqlalchemy import and_, case, func, literal, select, text

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
    ):
        fifteen_min_ago = func.date_sub(func.now(), text("INTERVAL 15 MINUTE"))
        two_weeks_ago = func.date_sub(func.now(), text("INTERVAL 2 WEEK"))

        online_expr = case(
            (User.last_activity >= fifteen_min_ago, literal(1)), else_=literal(0)
        ).label("online")

        statement = (
            select(
                User.id,
                User.username,
                User.last_activity,
                online_expr,
                UserMeta._value.label("avatar_ext"),
            )
            .outerjoin(
                UserMeta,
                (User.id == UserMeta.user_id)
                & (UserMeta.key == UserMeta.MetaKeys.AVATAR_EXT.value),
            )
            .where(User.activated_on.is_not(None))
            .order_by(online_expr.desc(), User.username)
        )

        if not get_inactive:
            statement = statement.where(User.last_activity >= two_weeks_ago)

        return await self.db_session.execute(statement)
