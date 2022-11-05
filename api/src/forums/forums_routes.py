from fastapi import APIRouter, status

from globals import g
from helpers.cache import CacheKeys, get_objects_by_id, set_cache
from helpers.functions import error_response

from forums.models import Forum, Thread
from forums.serializers import ForumSerializer, ThreadSerializer
from forums import schemas
from forums.functions import has_permission
from games.models import Game
from permissions.models.permission import ForumPermissions

forums = APIRouter(prefix="/forums")


@forums.get("/{forum_id}")
def get_forums(forum_id: int = 0):
    forum = get_objects_by_id(forum_id, Forum, CacheKeys.FORUM_DETAILS.value)

    read_permission = has_permission(
        ForumPermissions.READ,
        g.current_user.id,
        forum,
        g.current_user.get_forum_permissions(),
    )
    if not read_permission:
        return error_response(status_code=status.HTTP_403_FORBIDDEN)

    serialized_forum = ForumSerializer(forum)

    threads = Thread.objects.filter(forum=forum).order_by("-createdAt")[
        :PAGINATE_PER_PAGE
    ]
    serialized_threads = ThreadSerializer(threads, many=True)

    return {"forum": serialized_forum.data, "threads": serialized_threads.data}


@forums.post("")
def create_forum(new_forum: schemas.CreateForumInput):
    invalid_values = {}
    try:
        parent: Forum = get_objects_by_id(
            new_forum.parent, Forum, CacheKeys.FORUM_DETAILS.value
        )
    except Forum.DoesNotExist:
        invalid_values["parent"] = f'parent "{new_forum.parent}" does not exist'

    moderate_permission = has_permission(
        ForumPermissions.MODERATE,
        g.current_user.id,
        parent,
        g.current_user.get_forum_permissions(),
    )
    if not moderate_permission:
        return error_response(status_code=status.HTTP_403_FORBIDDEN)

    game = None
    if new_forum.gameId:
        game: Game = get_objects_by_id(
            new_forum.game_id, Game, CacheKeys.GAME_DETAILS.value
        )
        if not game:
            invalid_values["game_id"] = f'game_id "{new_forum.game_id}" does not exist'
    if invalid_values:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"invalid_values": invalid_values},
        )

    forum_values = {
        "title": new_forum.title,
        "forumType": new_forum.forumType,
        "parent": parent,
    }
    if new_forum.description:
        forum_values["description"] = new_forum.description
    if game:
        forum_values["game"] = game

    forum = Forum(**forum_values)
    forum.save()
    forum.generate_heritage()
    forum.save()
    return {"forum": {"id": forum.id, "title": forum.title}}


@forums.patch("/{forum_id}")
def update_forum(forum_id: int, forum_updates: schemas.UpdateForumInput):
    try:
        forum: Forum = get_objects_by_id(forum_id, Forum, CacheKeys.FORUM_DETAILS.value)
    except Forum.DoesNotExist:
        return error_response(status_code=status.HTTP_404_NOT_FOUND)

    moderate_permission = has_permission(
        ForumPermissions.MODERATE,
        g.current_user.id,
        forum,
        g.current_user.get_forum_permissions(),
    )
    if not moderate_permission:
        return error_response(status_code=status.HTTP_403_FORBIDDEN)

    invalid_values = {}
    if forum_updates.parent:
        try:
            parent: Forum = get_objects_by_id(
                forum_updates.parent, Forum, CacheKeys.FORUM_DETAILS.value
            )
            forum.parent = parent
        except Forum.DoesNotExist:
            invalid_values["parent"] = f'parent "{forum_updates.parent}" does not exist'
    for key in ["title", "description", "forumType", "parent", "order"]:
        if value := getattr(forum_updates, key, None):
            setattr(forum, key, value)
    forum.generate_heritage()
    forum.save()
    set_cache(CacheKeys.FORUM_DETAILS.value, {"id": forum.id}, forum)
    serialized_forum = ForumSerializer(forum)

    return {"updated": True, "forum": serialized_forum.data}
