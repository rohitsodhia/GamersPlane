from fastapi import APIRouter, status

from app.database import DBSessionDependency
from app.helpers.decorators import public
from app.helpers.functions import error_response
from app.middleware import AuthedUser
from app.repositories.legacy.user_repository import UserRepository
from app.users import legacy_schemas

users = APIRouter(prefix="/legacy/users")


@users.get(
    "/me",
    response_model=legacy_schemas.GetCurrentUserResponse,
)
@public
async def login(db_session: DBSessionDependency, authed_user: AuthedUser):
    user_repository = UserRepository(db_session, authed_user)
    user = await user_repository.get_user(authed_user.id, include_meta=True)

    if not user:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND, content={"noUser": True}
        )

    response = {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "joinDate": user.join_date,
        "activatedOn": user.activated_on,
        "usermeta": user.meta,
        "acpPermissions": [],
    }
