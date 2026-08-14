from fastapi import APIRouter

from app.database import DBSessionDependency
from app.exceptions import NotFoundException
from app.forums import schemas
from app.forums.functions import build_forum_tree, get_heritage
from app.helpers.decorators import public
from app.middleware import Auth
from app.repositories import ForumRepository, ThreadRepository

forums = APIRouter(prefix="/forums")


@forums.get(
    "/{forum_id}/breadcrumbs", response_model=schemas.GetForumBreadcrumbsResponse
)
@public
async def get_forum_breadcrumbs(
    forum_id: int, db_session: DBSessionDependency, auth: Auth
):
    forum_repository = ForumRepository(db_session, auth=auth)
    forum = await forum_repository.get(forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")

    heritage_forums = await get_heritage(forum_repository, forum.heritage)
    heritage_forums_data = [
        schemas.HeritageForumData(id=heritage_forum.id, title=heritage_forum.title)
        for heritage_forum in heritage_forums
    ]

    return schemas.GetForumBreadcrumbsResponse(
        id=forum.id,
        title=forum.title,
        heritage=heritage_forums_data,
    )


@forums.get("/{forum_id}")
@public
async def get_forum(forum_id: int, db_session: DBSessionDependency, auth: Auth):
    forum_repository = ForumRepository(db_session, auth=auth)
    forum = await forum_repository.get(forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")

    heritage_forums = await get_heritage(forum_repository, forum.heritage)
    heritage_forums_data = [
        schemas.HeritageForumData(id=heritage_forum.id, title=heritage_forum.title)
        for heritage_forum in heritage_forums
    ]

    descendants = list(await forum_repository.get_descendants(forum_id))

    thread_repository = ThreadRepository(db_session, auth=auth)
    last_posts_by_forum_id = await thread_repository.get_last_posts_by_forum_ids(
        [descendant.id for descendant in descendants]
    )

    children_forums_data = build_forum_tree(
        descendants, forum_id, last_posts_by_forum_id
    )

    return schemas.GetForum(
        id=forum.id,
        title=forum.title,
        description=forum.description,
        forum_type=forum.forum_type,
        parent_id=forum.parent_id,
        heritage=heritage_forums_data,
        order=forum.order,
        game_id=forum.game_id,
        thread_count=forum.thread_count,
        children=children_forums_data,
    )
