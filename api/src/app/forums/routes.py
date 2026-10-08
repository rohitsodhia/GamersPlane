from fastapi import APIRouter

from app.database import DBSessionDependency
from app.exceptions import NotFoundException
from app.forums import schemas
from app.forums.functions import build_forum_tree, get_heritage, prune_unreadable
from app.forums.permissions import ForumPermissions, Verbs
from app.helpers.decorators import public
from app.middleware import Principal
from app.repositories import ForumRepository, GameRepository, ThreadRepository
from app.repositories.game_repository import GAMES_ROOT_FORUM_ID

forums = APIRouter(prefix="/forums")


@forums.get(
    "/{forum_id}/breadcrumbs", response_model=schemas.GetForumBreadcrumbsResponse
)
@public
async def get_forum_breadcrumbs(
    forum_id: int, db_session: DBSessionDependency, principal: Principal
):
    forum_repository = ForumRepository(db_session, principal=principal)
    forum = await forum_repository.get(forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")
    await ForumPermissions.require_read(db_session, principal, forum, "Forum not found")

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
async def get_forum(
    forum_id: int, db_session: DBSessionDependency, principal: Principal
):
    forum_repository = ForumRepository(db_session, principal=principal)
    forum = await forum_repository.get(forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")

    heritage_forums = await get_heritage(forum_repository, forum.heritage)
    heritage_forums_data = [
        schemas.HeritageForumData(id=heritage_forum.id, title=heritage_forum.title)
        for heritage_forum in heritage_forums
    ]

    # The games forum holds every game's forum; listing it (or the index above
    # it) shows only the games the user plays in or has favorited.
    only_game_ids = None
    if forum_id in (0, GAMES_ROOT_FORUM_ID):
        only_game_ids = (
            await GameRepository(
                db_session, principal=principal
            ).get_forum_listed_game_ids(principal.id)
            if principal
            else set()
        )
    descendants = list(
        await forum_repository.get_descendants(forum_id, only_game_ids=only_game_ids)
    )

    permissions = await ForumPermissions.load(
        db_session, principal, [forum, *descendants]
    )
    readable_ids = {
        candidate.id
        for candidate in descendants
        if permissions.has(candidate, Verbs.FORUM_READ)
    }
    descendants = prune_unreadable(descendants, forum_id, readable_ids)
    forum_permissions = permissions.allowed(forum)
    if Verbs.FORUM_READ not in forum_permissions and not descendants:
        raise NotFoundException("Forum not found")

    thread_repository = ThreadRepository(db_session, principal=principal)
    last_posts_by_forum_id = await thread_repository.get_last_posts_by_forum_ids(
        list(readable_ids)
    )

    children_forums_data = build_forum_tree(
        descendants, forum_id, last_posts_by_forum_id, readable_ids
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
        thread_count=forum.thread_count if Verbs.FORUM_READ in forum_permissions else 0,
        permissions=sorted(verb.value for verb in forum_permissions),
        children=children_forums_data,
    )
