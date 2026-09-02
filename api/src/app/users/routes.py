from datetime import date

from fastapi import APIRouter, status

from app.configs import configs
from app.database import DBSessionDependency
from app.helpers.decorators import public, requires
from app.helpers.functions import error_response
from app.middleware import Principal
from app.models import RolePermission, UserMeta
from app.repositories import PostRepository, UserRepository
from app.schemas import ErrorItem
from app.users import schemas
from app.users.functions import calculate_age

users = APIRouter(prefix="/users")


@users.get(
    "/search",
    response_model=schemas.SearchUserResponse,
)
async def search_user(
    db_session: DBSessionDependency,
    username: str | None = None,
    id: int | None = None,
):
    user_repository = UserRepository(db_session)

    if id is not None:
        user = await user_repository.get_user_by_id(id)
    elif username is not None:
        user = await user_repository.get_user_by_username(username)
    else:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            errors=[
                ErrorItem(
                    code="missing_query",
                    detail="Either username or id must be provided",
                )
            ],
        )
    if not user:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            errors=[ErrorItem(code="user_not_found", detail="User not found")],
        )
    response = {
        "user": {
            "id": user.id,
            "username": user.username,
        }
    }
    return response


@users.get(
    "/autocomplete",
    response_model=schemas.SearchUsersResponse,
)
async def autocomplete_users(
    db_session: DBSessionDependency,
    username: str,
    limit: int = 10,
):
    user_repository = UserRepository(db_session)
    users = await user_repository.search_users_by_username_prefix(
        username, limit=min(limit, 25)
    )
    return {"users": [{"id": user.id, "username": user.username} for user in users]}


@users.get(
    "",
    response_model=schemas.GetUsersResponse,
    response_model_exclude_none=True,
)
@requires("manage_users")
async def get_users(
    db_session: DBSessionDependency,
    principal: Principal,
    prefix: str | None = None,
    banned: bool | None = None,
    page: int = 1,
    full: bool = False,
):
    if page < 1:
        page = 1
    # `full` data is admin-only; downgrade rather than reject so a plain
    # manage_users holder still gets the lightweight list.
    if full and not principal.has_global_permission(
        RolePermission.ValidPermissions.ADMIN.value
    ):
        full = False

    user_repository = UserRepository(db_session)
    found_users = await user_repository.get_users(
        prefix=prefix,
        banned=banned,
        page=page,
        limit=configs.PAGINATE_PER_PAGE,
    )
    count = await user_repository.count_users(prefix=prefix, banned=banned)

    users_data: list[dict] = []
    for user in found_users:
        user_data = {
            "id": user.id,
            "username": user.username,
            "avatar": user.avatar_url,
            "joinDate": user.join_date,
            "lastActivity": user.last_activity,
            "activated": user.activated_on is not None,
            "banned": user.banned,
        }
        if full:
            meta_by_key = {meta.key: meta.value for meta in user.meta}
            show_age = bool(meta_by_key.get(UserMeta.MetaKeys.SHOW_AGE.value))
            birthday = meta_by_key.get(UserMeta.MetaKeys.BIRTHDAY.value)
            user_data.update(
                {
                    "pronouns": meta_by_key.get(UserMeta.MetaKeys.PRONOUNS.value),
                    "showAge": show_age,
                    "age": (
                        str(calculate_age(date.fromisoformat(str(birthday))))
                        if show_age and birthday
                        else None
                    ),
                    "location": meta_by_key.get(UserMeta.MetaKeys.LOCATION.value),
                }
            )
        users_data.append(user_data)

    return {"users": users_data, "count": count, "page": page}


@users.patch(
    "/{id}/ban",
    response_model=schemas.BanUserResponse,
)
@requires("manage_users")
async def ban_user(
    id: int,
    db_session: DBSessionDependency,
):
    if id == 1:
        return error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            errors=[
                ErrorItem(
                    code="user_not_bannable",
                    detail="This user cannot be banned",
                )
            ],
        )

    user_repository = UserRepository(db_session)
    user = await user_repository.get_user(id)
    if not user:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            errors=[ErrorItem(code="user_not_found", detail="User not found")],
        )

    banned = await user_repository.toggle_ban(user)
    return {"banned": banned}


@users.get(
    "/{id}",
    response_model=schemas.GetUserResponse,
)
@public
async def get_user(id: int, db_session: DBSessionDependency, principal: Principal):
    user_repository = UserRepository(db_session)

    user = await user_repository.get_user_by_id(id, include_meta=True)
    if not user:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            errors=[ErrorItem(code="user_not_found", detail="User not found")],
        )

    meta_by_key = {meta.key: meta.value for meta in user.meta}
    show_age = bool(meta_by_key.get(UserMeta.MetaKeys.SHOW_AGE.value))
    birthday = meta_by_key.get(UserMeta.MetaKeys.BIRTHDAY.value)
    age = (
        str(calculate_age(date.fromisoformat(str(birthday))))
        if show_age and birthday
        else None
    )

    post_repository = PostRepository(db_session, principal=principal)
    game_post_count, community_post_count = await post_repository.count_by_author(
        user.id
    )

    response = {
        "user": {
            "id": user.id,
            "username": user.username,
            "avatar": user.avatar_url,
            "joinDate": user.join_date,
            "lastActivity": user.last_activity,
            "banned": user.banned,
            "pronouns": meta_by_key.get(UserMeta.MetaKeys.PRONOUNS.value),
            "showAge": show_age,
            "age": age,
            "location": meta_by_key.get(UserMeta.MetaKeys.LOCATION.value),
            "postCount": game_post_count + community_post_count,
            "communityPostCount": community_post_count,
            "gamePostCount": game_post_count,
            "activeGames": [],
            "characters": {"count": 0, "systems": []},
            "gmStats": {"count": 0, "systems": []},
        }
    }
    return response
