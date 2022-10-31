from typing import Optional
from django.core.cache import cache

from forums.models.forum import FORUM_PERMISSIONS, Forum
from helpers.cache import CacheKeys, generate_cache_id
from permissions.models.permission import (
    FORUM_PERMISSION_PREFIX,
    ForumPermissions,
    Permission,
)


def _build_forum_permissions(forum: Forum, permissions: list[Permission]) -> dict:
    permissions_dict = {permission.value: None for permission in ForumPermissions}
    calculated_permissions = {
        forum_id: permissions_dict.copy() for forum_id in forum.heritage
    }

    permission_starts = [
        f"{FORUM_PERMISSION_PREFIX}{id}_" for id in forum.heritage + forum.children
    ]
    forum_permissions = [
        permission
        for permission in permissions
        if permission.startswith(tuple(permission_starts))
    ]

    for permission in forum_permissions:
        _, forum_id, grant, *permission_val = permission.split("_")
        forum_id = int(forum_id)
        permission_val = "_".join(permission_val)
        if grant == "revoke":
            calculated_permissions[forum_id][permission_val] = False
        elif (
            calculated_permissions[forum_id][permission_val] is None and grant == "add"
        ):
            calculated_permissions[forum_id][permission_val] = True

    for forum_id in forum.heritage:
        for k, v in calculated_permissions[forum_id].items():
            if v == False:
                permissions_dict[k] = False
            elif v == True and permissions_dict[k] != False:
                permissions_dict[k] = True

    permissions_dict = {
        permission: bool(value) for permission, value in permissions_dict.items()
    }

    return permissions_dict


def get_forum_permissions(
    user_id: int, forum: Forum, permissions: list[Permission]
) -> dict:
    cache_id = generate_cache_id(
        CacheKeys.USER_FORUM_PERMISSIONS.value,
        {"user_id": user_id, "forum_id": forum.id},
    )
    forum_permissions = cache.get(cache_id)
    if forum_permissions is None:
        forum_permissions = _build_forum_permissions(forum, permissions)
        if forum_permissions:
            cache.set(cache_id, forum_permissions)

    return forum_permissions


def has_permission(
    permission: ForumPermissions,
    user_id: int,
    forum: Forum,
    permissions: list[Permission],
) -> Optional[bool]:
    forum_permissions = get_forum_permissions(user_id, forum, permissions)
    return forum_permissions[permission.value]