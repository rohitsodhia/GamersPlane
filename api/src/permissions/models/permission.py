from enum import Enum

from django.db import models


FORUM_PERMISSION_PREFIX = "forum_"


class ValidPermissions(Enum):
    ROLE_ADMIN = "role_admin_{role_id}"
    FORUM_ADD_MODERATE = "{FORUM_PERMISSION_PREFIX}{}_moderate_add"
    FORUM_REVOKE_MODERATE = "{FORUM_PERMISSION_PREFIX}{}_moderate_revoke"
    FORUM_ADD_READ = "{FORUM_PERMISSION_PREFIX}{}_read_add"
    FORUM_REVOKE_READ = "{FORUM_PERMISSION_PREFIX}{}_read_revoke"
    FORUM_ADD_WRITE = "{FORUM_PERMISSION_PREFIX}{}_write_add"
    FORUM_REVOKE_WRITE = "{FORUM_PERMISSION_PREFIX}{}_write_revoke"
    FORUM_ADD_EDIT = "{FORUM_PERMISSION_PREFIX}{}_edit_add"
    FORUM_REVOKE_EDIT = "{FORUM_PERMISSION_PREFIX}{}_edit_revoke"
    FORUM_ADD_DELETE = "{FORUM_PERMISSION_PREFIX}{}_delete_add"
    FORUM_REVOKE_DELETE = "{FORUM_PERMISSION_PREFIX}{}_delete_revoke"
    FORUM_ADD_CREATE_THREAD = "{FORUM_PERMISSION_PREFIX}{}_create_thread_add"
    FORUM_REVOKE_CREATE_THREAD = "{FORUM_PERMISSION_PREFIX}{}_create_thread_revoke"
    FORUM_ADD_DELETE_THREAD = "{FORUM_PERMISSION_PREFIX}{}_delete_thread_add"
    FORUM_REVOKE_DELETE_THREAD = "{FORUM_PERMISSION_PREFIX}{}_delete_thread_revoke"
    FORUM_ADD_ROLLS = "{FORUM_PERMISSION_PREFIX}{}_rolls_add"
    FORUM_REVOKE_ROLLS = "{FORUM_PERMISSION_PREFIX}{}_rolls_revoke"
    FORUM_ADD_POLL = "{FORUM_PERMISSION_PREFIX}{}_poll_add"
    FORUM_REVOKE_POLL = "{FORUM_PERMISSION_PREFIX}{}_poll_revoke"
    FORUM_ADD_DRAWS = "{FORUM_PERMISSION_PREFIX}{}_draws_add"
    FORUM_REVOKE_DRAWS = "{FORUM_PERMISSION_PREFIX}{}_draws_revoke"


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

    def save(self, **kwargs) -> None:
        if not self._valid_permission:
            raise ValueError(f"Permission not set through set_permission")
        return super().save(**kwargs)
