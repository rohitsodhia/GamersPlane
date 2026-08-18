from datetime import date

from fastapi import APIRouter, status

from app.database import DBSessionDependency
from app.helpers.decorators import public
from app.helpers.functions import error_response
from app.middleware import Auth
from app.models import UserMeta
from app.repositories import PostRepository, UserRepository
from app.schemas import ErrorItem
from app.users import schemas
from app.users.functions import calculate_age

users = APIRouter(prefix="/users")


@users.get(
    "/search",
    response_model=schemas.SearchUserResponse,
)
async def search_user(username: str, db_session: DBSessionDependency):
    user_repository = UserRepository(db_session)

    user = await user_repository.get_user_by_username(username)
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
    "/{id}",
    response_model=schemas.GetUserResponse,
)
@public
async def get_user(id: int, db_session: DBSessionDependency, auth: Auth):
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

    post_repository = PostRepository(db_session, auth=auth)
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
