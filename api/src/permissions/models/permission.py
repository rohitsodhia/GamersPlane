from enum import Enum

from django.db import models


FORUM_PERMISSION_PREFIX = "forum_"


class ForumPermissions(Enum):
    MODERATE = "moderate"
    READ = "read"
    WRITE = "write"
    EDIT = "edit"
    DELETE = "delete"
    CREATE_THREAD = "create_thread"
    DELETE_THREAD = "delete_thread"
    ROLLS = "rolls"
    POLL = "poll"
    DRAWS = "draws"


ValidPermissions = Enum(
    "ValidPermissions",
    {"ROLE_ADMIN": "role_admin_{role_id}"}
    | {
        f"FORUM_ADD_{permission.name}": FORUM_PERMISSION_PREFIX
        + "{forum_id}_add_"
        + permission.value
        for permission in ForumPermissions
    }
    | {
        f"FORUM_REVOKE_{permission.name}": FORUM_PERMISSION_PREFIX
        + "{forum_id}_revoke_"
        + permission.value
        for permission in ForumPermissions
    },
)


class Permission(models.Model):
    class Meta:
        db_table = "permissions"

    permission = models.CharField(max_length=64, unique=True)

    def __init__(self, *args, **kwargs) -> None:
        self._valid_permission = False
        super().__init__(*args, **kwargs)

    def set_permission(self, permission: ValidPermissions, **kwargs):
        if type(permission) is not ValidPermissions:
            raise ValueError(f"'{permission}' is not a ValidPermission")

        if "{" in permission.value:
            self.permission = permission.value.format(**kwargs)
        else:
            self.permission = permission.value
        self._valid_permission = True

    def save(self, **kwargs) -> None:
        if not self._valid_permission:
            raise ValueError(f"Permission not set through set_permission")
        return super().save(**kwargs)
