from enum import Enum

from django.db import models


class ValidPermissions(Enum):
    ROLE_ADMIN = "role_admin_{role_id}"
    FORUM_ADD_MODERATE = "forum_{}_moderate_add"
    FORUM_REVOKE_MODERATE = "forum_{}_moderate_revoke"
    FORUM_ADD_READ = "forum_{}_read_add"
    FORUM_REVOKE_READ = "forum_{}_read_revoke"
    FORUM_ADD_WRITE = "forum_{}_write_add"
    FORUM_REVOKE_WRITE = "forum_{}_write_revoke"
    FORUM_ADD_EDIT = "forum_{}_edit_add"
    FORUM_REVOKE_EDIT = "forum_{}_edit_revoke"
    FORUM_ADD_DELETE = "forum_{}_delete_add"
    FORUM_REVOKE_DELETE = "forum_{}_delete_revoke"
    FORUM_ADD_CREATE_THREAD = "forum_{}_create_thread_add"
    FORUM_REVOKE_CREATE_THREAD = "forum_{}_create_thread_revoke"
    FORUM_ADD_DELETE_THREAD = "forum_{}_delete_thread_add"
    FORUM_REVOKE_DELETE_THREAD = "forum_{}_delete_thread_revoke"
    FORUM_ADD_ROLLS = "forum_{}_rolls_add"
    FORUM_REVOKE_ROLLS = "forum_{}_rolls_revoke"
    FORUM_ADD_POLL = "forum_{}_poll_add"
    FORUM_REVOKE_POLL = "forum_{}_poll_revoke"
    FORUM_ADD_DRAWS = "forum_{}_draws_add"
    FORUM_REVOKE_DRAWS = "forum_{}_draws_revoke"


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
