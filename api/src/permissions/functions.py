from permissions.models import Permission
from permissions.models.permission import ValidPermissions


def create_permission(permission: ValidPermissions, **kwargs) -> Permission:
    permission_obj = Permission()
    permission_obj.set_permission(permission, **kwargs)
    permission_obj.save()
    return permission_obj
