from app.database import DBSessionDependency
from app.models.legacy import Forum, ForumGroup, User


class ForumRepository:
    def __init__(
        self, db_session: DBSessionDependency, authed_user: User | None = None
    ):
        self.db_session = db_session
        self.authed_user = authed_user

    async def create_forum(
        self,
        *_,
        title: str,
        description: str = "",
        forum_type: Forum.ForumTypes,
        parent_id: int,
        order: int,
    ):
        forum = Forum(
            title=title,
            description=description,
            forum_type=forum_type,
            parent_id=parent_id,
            order=order,
        )
        self.db_session.add(forum)
        # await self.db_session.flush()

        return forum

    async def create_forum_group(
        self,
        *_,
        name: str,
        status: bool = True,
        owner_id: int,
    ):
        forum_group = ForumGroup(name=name, status=status, owner_id=owner_id)
        self.db_session.add(forum_group)
        # await self.db_session.flush()

        return forum_group
