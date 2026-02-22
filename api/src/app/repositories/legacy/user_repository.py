from sqlalchemy import and_, select

from app.database import DBSessionDependency
from app.models.legacy import User, UserMeta


class UserRepository:
    def __init__(
        self,
        db_session: DBSessionDependency,
        authed_user: User | None = None,
    ):
        self.db_session = db_session
        self.authed_user = authed_user

    async def get_avatar(
        self,
        user_id: int,
    ):
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

        if avatar_ext:
            avatar = f"/ucp/avatars/{user_id}.{avatar_ext}"
        else:
            avatar = "/ucp/avatars/avatar.png"

        return avatar
