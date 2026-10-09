from typing import Annotated, Literal

from pydantic import StringConstraints

from app.models import RolePermission
from app.schema_base import SchemaBase

# Matches the roles.name column.
GameRoleName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
Effect = Literal["allow", "deny"]


class VerbData(SchemaBase):
    value: str
    label: str


class PermissionRoleData(SchemaBase):
    id: int
    name: str
    kind: Literal["player", "custom", "registered", "guest", "site"]
    # Verb -> this role's grant on this forum. A verb with no grant is absent.
    grants: dict[str, Effect]
    # Verb -> whether the role alone resolves to it from the ancestors' grants.
    inherited: dict[str, bool]


class GetForumPermissionsResponse(SchemaBase):
    can_grant_moderate: bool
    verbs: list[VerbData]
    roles: list[PermissionRoleData]


class RolePermissionsInput(SchemaBase):
    role_id: int
    # Verb -> effect. A verb left out inherits (no grant). Keys are checked
    # against the forum verbs by the repository.
    grants: dict[str, RolePermission.Effects]


class SetForumPermissionsInput(SchemaBase):
    roles: list[RolePermissionsInput]


class RoleSearchData(SchemaBase):
    id: int
    name: str


class SearchPermissionRolesResponse(SchemaBase):
    roles: list[RoleSearchData]


class MemberData(SchemaBase):
    id: int
    username: str


class GameRoleData(SchemaBase):
    id: int
    name: str
    kind: Literal["player", "custom"]
    members: list[MemberData]


class GetGameRolesResponse(SchemaBase):
    roles: list[GameRoleData]
    players: list[MemberData]


class GameRoleInput(SchemaBase):
    name: GameRoleName


class RoleIdResponse(SchemaBase):
    id: int


class SetRoleMembersInput(SchemaBase):
    user_ids: list[int]
