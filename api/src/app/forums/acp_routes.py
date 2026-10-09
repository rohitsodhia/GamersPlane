from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import DBSessionDependency
from app.exceptions import ValidationError
from app.forums import acp_schemas as schemas
from app.forums.functions import is_game_root_forum
from app.forums.permissions import FORUM_VERBS_ORDERED, ForumPermissions, Verbs
from app.forums.routes import get_forum_or_404
from app.middleware import Principal
from app.models import Forum, Game, User
from app.repositories import ForumACPRepository, ForumRepository, RBACkRepository

forums_acp = APIRouter(prefix="/forums")


async def get_moderated_forum(
    forum_id: int, db_session: AsyncSession, principal: User
) -> Forum:
    forum = await get_forum_or_404(ForumRepository(db_session, principal), forum_id)
    await ForumPermissions.require_moderate(db_session, principal, forum)
    return forum


async def get_moderated_game(
    forum_id: int, db_session: AsyncSession, principal: User
) -> Game:
    """The game whose root forum this is, for a moderator of that forum."""
    forum = await get_moderated_forum(forum_id, db_session, principal)
    if not is_game_root_forum(forum):
        raise ValidationError("Roles are managed on the game's forum")
    return await ForumACPRepository(db_session, principal).get_game(forum.game_id)


def is_admin(principal: User) -> bool:
    return principal.has_global_permission(Verbs.ADMIN.value)


@forums_acp.get(
    "/{forum_id}/permissions", response_model=schemas.GetForumPermissionsResponse
)
async def get_forum_permissions(
    forum_id: int, db_session: DBSessionDependency, principal: Principal
):
    forum = await get_moderated_forum(forum_id, db_session, principal)
    rows = await ForumACPRepository(db_session, principal).get_permission_rows(forum)
    return schemas.GetForumPermissionsResponse(
        can_grant_moderate=is_admin(principal),
        verbs=[
            schemas.VerbData(value=verb.value, label=verb.label)
            for verb in FORUM_VERBS_ORDERED
        ],
        roles=[
            schemas.PermissionRoleData(
                id=role.id,
                name=role.name,
                kind=kind,
                grants=grants,
                inherited=inherited,
            )
            for role, kind, grants, inherited in rows
        ],
    )


@forums_acp.put("/{forum_id}/permissions", status_code=status.HTTP_204_NO_CONTENT)
async def set_forum_permissions(
    forum_id: int,
    data: schemas.SetForumPermissionsInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    forum = await get_moderated_forum(forum_id, db_session, principal)
    await ForumACPRepository(db_session, principal).set_permissions(
        forum,
        [(entry.role_id, entry.grants) for entry in data.roles],
        can_grant_moderate=is_admin(principal),
    )


@forums_acp.get(
    "/{forum_id}/permissions/roles",
    response_model=schemas.SearchPermissionRolesResponse,
)
async def search_permission_roles(
    forum_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
    name_filter: Annotated[str | None, Query(alias="filter")] = None,
):
    forum = await get_moderated_forum(forum_id, db_session, principal)
    if forum.game_id is not None:
        raise ValidationError("A game's forums only use the game's roles")
    roles = await ForumACPRepository(db_session, principal).search_site_roles(
        name_filter
    )
    return schemas.SearchPermissionRolesResponse(
        roles=[schemas.RoleSearchData(id=role.id, name=role.name) for role in roles]
    )


@forums_acp.get("/{forum_id}/roles", response_model=schemas.GetGameRolesResponse)
async def get_game_roles(
    forum_id: int, db_session: DBSessionDependency, principal: Principal
):
    game = await get_moderated_game(forum_id, db_session, principal)
    acp_repository = ForumACPRepository(db_session, principal)
    roles = await acp_repository.get_game_roles(game)
    players = await acp_repository.get_accepted_players(game)
    return schemas.GetGameRolesResponse(
        roles=[
            schemas.GameRoleData(
                id=role.id,
                name=role.name,
                kind="player" if role.id == game.player_role_id else "custom",
                members=[
                    schemas.MemberData(id=member.id, username=member.username)
                    for member in sorted(role.users, key=lambda user: user.username)
                ],
            )
            for role in roles
        ],
        players=[
            schemas.MemberData(id=player.id, username=player.username)
            for player in players
        ],
    )


@forums_acp.post("/{forum_id}/roles", response_model=schemas.RoleIdResponse)
async def create_game_role(
    forum_id: int,
    data: schemas.GameRoleInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game = await get_moderated_game(forum_id, db_session, principal)
    role = await ForumACPRepository(db_session, principal).create_game_role(
        game, data.name
    )
    return schemas.RoleIdResponse(id=role.id)


@forums_acp.patch("/{forum_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def rename_game_role(
    forum_id: int,
    role_id: int,
    data: schemas.GameRoleInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game = await get_moderated_game(forum_id, db_session, principal)
    role = await ForumACPRepository(db_session, principal).get_custom_role(
        game, role_id
    )
    await RBACkRepository(db_session, principal).update_role(role, name=data.name)


@forums_acp.delete(
    "/{forum_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_game_role(
    forum_id: int,
    role_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game = await get_moderated_game(forum_id, db_session, principal)
    role = await ForumACPRepository(db_session, principal).get_custom_role(
        game, role_id
    )
    await RBACkRepository(db_session, principal).delete_role(role)


@forums_acp.put(
    "/{forum_id}/roles/{role_id}/members", status_code=status.HTTP_204_NO_CONTENT
)
async def set_game_role_members(
    forum_id: int,
    role_id: int,
    data: schemas.SetRoleMembersInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    game = await get_moderated_game(forum_id, db_session, principal)
    acp_repository = ForumACPRepository(db_session, principal)
    role = await acp_repository.get_custom_role(game, role_id)
    await acp_repository.set_role_members(game, role, data.user_ids)
