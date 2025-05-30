from database import DBSessionDependency
from fastapi import APIRouter, Request
from models import Permission, Role, User
from permissions import schemas
from sqlalchemy import select

roles = APIRouter(prefix="/roles")


@roles.get("/", response_model=schemas.RoleListResponse)
async def list_roles(
    request: Request,
    db_session: DBSessionDependency,
    filter: str | None = None,
    all: bool = False,
):
    get_roles = select(Role)
    if filter:
        get_roles = get_roles.where(Role.name.ilike(f"%{filter}%"))
    if not all and request.user.roles.contains("admin"):
        get_roles = get_roles.where(User.id == request.user.user.id)
    roles = await db_session.scalars(get_roles)
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
                "member": request.user.id in role.users,
                "admin": request.user.admin,
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


# @roles.get("/{user_id}", response_model=schemas.RoleListResponse)
# @logged_in(permissions="manage_users")
# def list_user_roles(user_id: int):
#     user = User.objects.get(id=user_id)
#     roles_list = []
#     for role in user.roles.all():
#         roles_list.append(
#             {
#                 "id": role.id,
#                 "name": role.name,
#                 "owner": {
#                     "id": role.owner.id,
#                     "username": role.owner.username,
#                 },
#                 "member": bool(role.users.filter(id=g.current_user.id)),
#                 "admin": g.current_user.admin,
#             }
#         )
#     role_admins = []
#     for permission in user.permissions:
#         if permission.startswith(ValidPermissions.ROLE_ADMIN.value[0]):
#             role_admins.append(int(permission.split("_")[2]))
#     for role in roles_list:
#         if role["id"] in role_admins:
#             role["admin"] = True

#     return {"roles": roles_list}
