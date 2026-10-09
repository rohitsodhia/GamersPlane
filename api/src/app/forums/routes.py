from fastapi import APIRouter, status

from app.database import DBSessionDependency
from app.exceptions import ForbiddenException, NotFoundException
from app.forums import schemas
from app.forums.functions import (
    build_forum_tree,
    build_moderated_tree,
    get_heritage,
    is_game_root_forum,
    prune_unreadable,
)
from app.forums.permissions import ForumPermissions, Verbs, moderated_roots
from app.helpers.decorators import public
from app.middleware import Principal
from app.models import Forum
from app.repositories import ForumRepository, GameRepository, ThreadRepository
from app.repositories.forum_repository import PROTECTED_FORUM_IDS, SITE_ROOT_FORUM_ID
from app.repositories.game_repository import GAMES_ROOT_FORUM_ID

forums = APIRouter(prefix="/forums")


def build_heritage_data(
    heritage_forums: list[Forum], permissions: ForumPermissions
) -> list[schemas.HeritageForumData]:
    return [
        schemas.HeritageForumData(
            id=heritage_forum.id,
            title=heritage_forum.title,
            moderate=permissions.has(heritage_forum, Verbs.FORUM_MODERATE),
        )
        for heritage_forum in heritage_forums
    ]


async def get_forum_or_404(forum_repository: ForumRepository, forum_id: int) -> Forum:
    forum = await forum_repository.get(forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")
    return forum


@forums.get("/moderated", response_model=list[schemas.ModeratedForumData])
async def get_moderated_forums(db_session: DBSessionDependency, principal: Principal):
    """The forums the principal moderates, nested under their ancestors.

    Game forums are only listed for games where the principal moderates one of
    the game's forums directly, so site-wide moderators don't get every game.
    """
    roots = await moderated_roots(db_session, principal)
    if not roots:
        return []

    forum_repository = ForumRepository(db_session, principal=principal)
    subtrees = list(
        await forum_repository.get_subtrees(
            [root.id for root in roots],
            only_game_ids={root.game_id for root in roots if root.game_id is not None},
        )
    )
    permissions = await ForumPermissions.load(db_session, principal, subtrees)
    moderated = [
        forum for forum in subtrees if permissions.has(forum, Verbs.FORUM_MODERATE)
    ]

    heading_ids = {forum_id for forum in moderated for forum_id in forum.heritage} - {
        forum.id for forum in subtrees
    }
    headings = (
        list(await forum_repository.get_multiple(list(heading_ids)))
        if heading_ids
        else []
    )

    return build_moderated_tree(
        [*subtrees, *headings], {forum.id for forum in moderated}
    )


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
    heritage_forums = await get_heritage(forum_repository, forum.heritage)
    permissions = await ForumPermissions.load(
        db_session, principal, [forum, *heritage_forums]
    )
    if not permissions.has(forum, Verbs.FORUM_READ):
        raise NotFoundException("Forum not found")

    return schemas.GetForumBreadcrumbsResponse(
        id=forum.id,
        title=forum.title,
        heritage=build_heritage_data(heritage_forums, permissions),
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
        db_session, principal, [forum, *descendants, *heritage_forums]
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
        heritage=build_heritage_data(heritage_forums, permissions),
        order=forum.order,
        game_id=forum.game_id,
        thread_count=forum.thread_count if Verbs.FORUM_READ in forum_permissions else 0,
        permissions=sorted(verb.value for verb in forum_permissions),
        children=children_forums_data,
    )


@forums.patch("/{forum_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_forum(
    forum_id: int,
    data: schemas.UpdateForumInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    forum_repository = ForumRepository(db_session, principal=principal)
    forum = await get_forum_or_404(forum_repository, forum_id)
    await ForumPermissions.require_moderate(db_session, principal, forum)

    if forum.id == SITE_ROOT_FORUM_ID:
        raise ForbiddenException("The forum index can't be edited")
    if is_game_root_forum(forum):
        raise ForbiddenException("A game's forum follows the game's details")
    if (
        data.title is not None
        and data.title != forum.title
        and forum.id in PROTECTED_FORUM_IDS
    ):
        raise ForbiddenException("This forum can't be renamed")

    await forum_repository.update(forum, title=data.title, description=data.description)


@forums.post("/{forum_id}/subforums", response_model=schemas.ForumIdResponse)
async def create_subforum(
    forum_id: int,
    data: schemas.CreateSubforumInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    forum_repository = ForumRepository(db_session, principal=principal)
    parent = await get_forum_or_404(forum_repository, forum_id)
    await ForumPermissions.require_moderate(db_session, principal, parent)

    forum = await forum_repository.add(
        title=data.title,
        description=data.description or None,
        forum_type=data.forum_type,
        parent_id=parent.id,
        game_id=parent.game_id,
    )
    return schemas.ForumIdResponse(id=forum.id)


@forums.put("/{forum_id}/subforums/order", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_subforums(
    forum_id: int,
    data: schemas.ReorderSubforumsInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    forum_repository = ForumRepository(db_session, principal=principal)
    parent = await get_forum_or_404(forum_repository, forum_id)
    await ForumPermissions.require_moderate(db_session, principal, parent)

    await forum_repository.reorder_children(parent.id, data.forum_ids)


@forums.delete("/{forum_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_forum(
    forum_id: int, db_session: DBSessionDependency, principal: Principal
):
    """Deleting a forum is managing its parent's subforums, so it takes
    moderation of the parent."""
    forum_repository = ForumRepository(db_session, principal=principal)
    forum = await get_forum_or_404(forum_repository, forum_id)
    if forum.id in PROTECTED_FORUM_IDS:
        raise ForbiddenException("This forum can't be deleted")
    parent = await get_forum_or_404(forum_repository, forum.parent_id)
    await ForumPermissions.require_moderate(db_session, principal, parent)
    if is_game_root_forum(forum):
        raise ForbiddenException("A game's forum is deleted with the game")

    await forum_repository.delete(forum)
