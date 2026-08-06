from typing import Annotated

import jwt
from fastapi import Depends, Request

from app.configs import configs
from app.database import DBSessionDependency
from app.exceptions import ForbiddenException
from app.models import User
from app.repositories.user_repository import UserRepository


async def authed_user(request: Request) -> User:
    return request.scope["user"]


AuthedUser = Annotated[User, Depends(authed_user)]


async def validate_jwt(request: Request, db_session: DBSessionDependency):
    token = request.headers.get("Authorization")
    request.scope["auth"] = None
    request.scope["user"] = None
    if token and token[:7] == "Bearer ":
        token = token[7:]
        try:
            jwt_body = jwt.decode(
                token,
                configs.JWT_SECRET_KEY,
                algorithms=[configs.JWT_ALGORITHM],
            )
            user_repository = UserRepository(db_session)
            user = await user_repository.get_user(jwt_body["user_id"])
            if user:
                await user_repository.update_last_activity(user)
                request.scope["auth"] = await user.awaitable_attrs.permissions
                request.scope["user"] = user
        except (jwt.InvalidSignatureError, jwt.ExpiredSignatureError, jwt.DecodeError):
            pass


async def check_authorization(request: Request):
    public = getattr(request.scope["route"].endpoint, "is_public", False)

    if not public and request.scope.get("user") is None:
        raise ForbiddenException()
