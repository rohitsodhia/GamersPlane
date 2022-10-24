import functools
from typing import Optional
from django.core.cache import cache

from forums.models.forum import FORUM_PERMISSIONS, Forum
from helpers.cache import CacheKeys, generate_cache_id
from permissions.models.permission import (
    ForumPermissions,
    Permission,
)
from forums.schemas import PermissionsDict


def _build_forum_permissions(forum: Forum, permissions: list[Permission]) -> dict:
    permissions_dict = {permission.value: None for permission in ForumPermissions}
    calculated_permissions = {
        forum_id: permissions_dict.copy() for forum_id in forum.heritage
    }

    permission_starts = [
        "{FORUM_PERMISSION_PREFIX}{id}_" for id in forum.heritage + forum.children
    ]
    forum_permissions = [
        permission
        for permission in permissions
        if permission.startswith(tuple(permission_starts))
    ]

    for permission in forum_permissions:
        _, forum_id, grant, *permission_val = permission.split("_")
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


@functools.cache
def forum_permissions(
    user_id: int, forum: Forum, permissions: list[Permission]
) -> dict:
    cache_id = generate_cache_id(
        CacheKeys.USER_FORUM_PERMISSIONS.value,
        {"user_id": user_id, "forum_id": forum.id},
    )

    return permissions


def has_permission(
    permission: ForumPermissions,
    user_id: int,
    forum: Forum,
    permissions: list[Permission],
) -> Optional(bool):
    forum_permissions = forum_permissions(user_id, forum, permissions)
    return forum_permissions[permission]
