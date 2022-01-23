from fastapi import APIRouter
from django.db import models

from globals import g
from helpers.decorators import logged_in

from users.models import User
from permissions.models import Role, Permission
from permissions.models.permission import ValidPermissions
from permissions import schemas

roles = APIRouter(prefix="/roles")


@roles.get("/", response_model=schemas.RoleListResponse)
@logged_in
def list_roles(filter: str = None, all: bool = False):
    roles = Role.objects
    if filter:
        roles = roles.filter(name__icontains=filter)
    if not all and not g.current_user.admin:
        roles = roles.filter(users__id=g.current_user.user.id)
    if not issubclass(type(roles), models.QuerySet):
        roles = roles.all()
    roles_list = []
    for role in roles:
        roles_list.append(
            {
                "id": role.id,
                "name": role.name,
                "owner": {
                    "id": role.owner.id,
                    "username": role.owner.username,
                },
                "member": bool(role.users.filter(id=g.current_user.id)),
                "admin": g.current_user.admin,
            }
        )
    role_admins = [
        int(permission.permission.split("_")[2])
        for permission in Permission.objects.filter(
            permission__startswith="role_admin_"
        )
    ]
    for role in roles_list:
        if role["id"] in role_admins:
            role["admin"] = True

    return {"roles": roles_list}


@roles.get("/{user_id}", response_model=schemas.RoleListResponse)
@logged_in(permissions="manage_users")
def list_user_roles(user_id: int):
    user = User.objects.get(id=user_id)
    roles_list = []
    for role in user.roles.all():
        roles_list.append(
            {
                "id": role.id,
                "name": role.name,
                "owner": {
                    "id": role.owner.id,
                    "username": role.owner.username,
                },
                "member": bool(role.users.filter(id=g.current_user.id)),
                "admin": g.current_user.admin,
            }
        )
    role_admins = []
    for permission in user.permissions:
        if permission.startswith(ValidPermissions.ROLE_ADMIN.value[0]):
            role_admins.append(int(permission.split("_")[2]))
    for role in roles_list:
        if role["id"] in role_admins:
            role["admin"] = True

    return {"roles": roles_list}
