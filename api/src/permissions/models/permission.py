from enum import Enum

from django.db import models


class ValidPermissions(Enum):
    ROLE_ADMIN = "role_admin_{role_id}"


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
