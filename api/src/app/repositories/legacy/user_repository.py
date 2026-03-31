from sqlalchemy import and_, select

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

