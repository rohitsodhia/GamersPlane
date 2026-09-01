from typing import Annotated

from fastapi import APIRouter, Query, status

from app.database import DBSessionDependency
from app.exceptions import NotFoundException
from app.helpers.decorators import requires
from app.middleware import Principal
from app.rbac import schemas
from app.repositories import RBACkRepository, UserRepository

rbac = APIRouter(prefix="/rbac")


def _grant_description(grant, scope_names: dict) -> str:
    """Human-readable summary of a grant: "{label} - {resource} (#{id})".

    Global grants (no scope) are just the permission label.
    """
    label = grant.permission.label
    if grant.scope_type is None:
        return label
    name = scope_names.get((grant.scope_type, grant.scope_id), "unknown")
    return f"{label} - {name} (#{grant.scope_id})"


@rbac.get("/permissions", response_model=schemas.GetPermissionsResponse)
def get_permissions(db_session: DBSessionDependency, principal: Principal):
    rbac_repository = RBACkRepository(db_session, principal=principal)
    return {"permissions": rbac_repository.get_permissions()}


@rbac.get("/roles", response_model=schemas.GetRolesResponse)
async def get_roles(
    db_session: DBSessionDependency,
    principal: Principal,
    name_filter: Annotated[str | None, Query(alias="filter")] = None,
    game_roles: Annotated[bool, Query()] = False,
):
    rbac_repository = RBACkRepository(db_session, principal=principal)
    roles = await rbac_repository.get_roles(name_filter, game_roles=game_roles)
    return {
        "roles": [
            schemas.RoleData(
                id=role.id,
                name=role.name,
                owner=schemas.UserData(
                    id=role.owner.id, username=role.owner.username
                ),
                user_count=len(role.users),
                grant_count=len(role.grants),
            )
            for role in roles
        ]
    }


@rbac.post("/roles", response_model=schemas.RoleIdResponse)
@requires("admin")
async def create_role(
    body: schemas.CreateRoleInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    owner_id = body.owner_id if body.owner_id is not None else principal.id
    if owner_id != principal.id:
        user_repository = UserRepository(db_session)
        if await user_repository.get_user(owner_id) is None:
            raise NotFoundException("Owner not found")

    rbac_repository = RBACkRepository(db_session, principal=principal)
    role = await rbac_repository.create_role(body.name, owner_id)
    return schemas.RoleIdResponse(id=role.id)


@rbac.get("/roles/{role_id}", response_model=schemas.GetRoleResponse)
async def get_role(
    role_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    rbac_repository = RBACkRepository(db_session, principal=principal)
    role = await rbac_repository.get_role(role_id)
    if role is None or not rbac_repository.can_manage_role(role.id):
        raise NotFoundException("Role not found")

    scope_names = await rbac_repository.get_scope_names(role.grants)
    return schemas.GetRoleResponse(
        id=role.id,
        name=role.name,
        owner=schemas.UserData(id=role.owner.id, username=role.owner.username),
        users=[
            schemas.UserData(id=user.id, username=user.username)
            for user in role.users
        ],
        grants=[
            schemas.GrantData(
                id=grant.id,
                permission=schemas.PermissionData(
                    value=grant.permission.value, label=grant.permission.label
                ),
                description=_grant_description(grant, scope_names),
                scope_type=grant.scope_type,
                scope_id=grant.scope_id,
                effect=grant.effect,
            )
            for grant in role.grants
        ],
    )


@rbac.patch("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
@requires("admin")
async def update_role(
    role_id: int,
    body: schemas.UpdateRoleInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    rbac_repository = RBACkRepository(db_session, principal=principal)
    role = await rbac_repository.get_role(role_id)
    if role is None:
        raise NotFoundException("Role not found")

    name = body.name if "name" in body.model_fields_set else None

    new_owner = None
    if (
        "owner_id" in body.model_fields_set
        and body.owner_id is not None
        and body.owner_id != role.owner_id
    ):
        new_owner = await UserRepository(db_session).get_user(body.owner_id)
        if new_owner is None:
            raise NotFoundException("Owner not found")

    await rbac_repository.update_role(role, name=name, owner=new_owner)


@rbac.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
@requires("admin")
async def delete_role(
    role_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    rbac_repository = RBACkRepository(db_session, principal=principal)
    role = await rbac_repository.get_role(role_id)
    if role is None:
        raise NotFoundException("Role not found")

    await rbac_repository.delete_role(role)


@rbac.post("/roles/{role_id}/grants", status_code=status.HTTP_204_NO_CONTENT)
@requires("admin")
async def create_grant(
    role_id: int,
    body: schemas.CreateGrantInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    rbac_repository = RBACkRepository(db_session, principal=principal)
    role = await rbac_repository.get_role(role_id)
    if role is None:
        raise NotFoundException("Role not found")

    await rbac_repository.create_grant(
        role,
        body.permission,
        body.scope_type,
        body.scope_id,
        body.effect,
    )


@rbac.patch(
    "/roles/{role_id}/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT
)
@requires("admin")
async def update_grant(
    role_id: int,
    grant_id: int,
    body: schemas.UpdateGrantInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    rbac_repository = RBACkRepository(db_session, principal=principal)
    role = await rbac_repository.get_role(role_id)
    if role is None:
        raise NotFoundException("Role not found")

    grant = rbac_repository.get_grant(role, grant_id)
    if grant is None:
        raise NotFoundException("Grant not found")

    await rbac_repository.update_grant(grant, body.effect)


@rbac.delete(
    "/roles/{role_id}/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT
)
@requires("admin")
async def delete_grant(
    role_id: int,
    grant_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    rbac_repository = RBACkRepository(db_session, principal=principal)
    role = await rbac_repository.get_role(role_id)
    if role is None:
        raise NotFoundException("Role not found")

    grant = rbac_repository.get_grant(role, grant_id)
    if grant is None:
        raise NotFoundException("Grant not found")

    await rbac_repository.delete_grant(role, grant)


@rbac.post("/roles/{role_id}/users", status_code=status.HTTP_204_NO_CONTENT)
@requires("admin")
async def add_user_to_role(
    role_id: int,
    body: schemas.AddUserToRoleInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    rbac_repository = RBACkRepository(db_session, principal=principal)
    role = await rbac_repository.get_role(role_id)
    if role is None:
        raise NotFoundException("Role not found")

    user_repository = UserRepository(db_session)
    user = await user_repository.get_user(body.user_id)
    if user is None:
        raise NotFoundException("User not found")

    await rbac_repository.add_user_to_role(role, user)


@rbac.delete(
    "/roles/{role_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
@requires("admin")
async def remove_user_from_role(
    role_id: int,
    user_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    rbac_repository = RBACkRepository(db_session, principal=principal)
    role = await rbac_repository.get_role(role_id)
    if role is None:
        raise NotFoundException("Role not found")

    await rbac_repository.remove_user_from_role(role, user_id)
