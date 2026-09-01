from typing import Annotated

from pydantic import StringConstraints, model_validator

from app.models import RolePermission
from app.schema_base import SchemaBase

RoleName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=48)
]


class UserData(SchemaBase):
    id: int
    username: str


class PermissionData(SchemaBase):
    value: str
    label: str


class PermissionWithScopesData(PermissionData):
    # Allowed scope types for this verb: ["global"] == unscoped-only, otherwise a
    # single scope type such as ["forum"] or ["role"].
    scopes: list[str] = []


class GetPermissionsResponse(SchemaBase):
    permissions: list[PermissionWithScopesData]


class RoleData(SchemaBase):
    id: int
    name: str
    owner: UserData
    user_count: int
    grant_count: int


class GetRolesResponse(SchemaBase):
    roles: list[RoleData]


class CreateRoleInput(SchemaBase):
    name: RoleName
    owner_id: int | None = None


class RoleIdResponse(SchemaBase):
    id: int


class GrantData(SchemaBase):
    id: int
    permission: PermissionData
    description: str | None = None
    scope_type: RolePermission.ScopeTypes | None = None
    scope_id: int | None = None
    effect: RolePermission.Effects


class GetRoleResponse(SchemaBase):
    id: int
    name: str
    owner: UserData
    users: list[UserData]
    grants: list[GrantData]


class UpdateRoleInput(SchemaBase):
    name: RoleName | None = None
    owner_id: int | None = None


class CreateGrantInput(SchemaBase):
    permission: RolePermission.ValidPermissions
    scope_type: RolePermission.ScopeTypes | None = None
    scope_id: int | None = None
    effect: RolePermission.Effects = RolePermission.Effects.ALLOW

    @model_validator(mode="after")
    def _scope_both_or_neither(self):
        if (self.scope_type is None) != (self.scope_id is None):
            raise ValueError("scope_type and scope_id must be set together")
        return self


class UpdateGrantInput(SchemaBase):
    effect: RolePermission.Effects


class AddUserToRoleInput(SchemaBase):
    user_id: int
