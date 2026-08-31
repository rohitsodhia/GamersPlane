from typing import Annotated

import jwt
from fastapi import Depends, Request

from app.configs import configs
from app.database import DBSessionDependency
from app.exceptions import ForbiddenException
from app.models import RolePermission, User
from app.repositories.user_repository import UserRepository

# Global superuser verb: holding it satisfies any @requires check. Delete this
# constant and the guard in check_authorization to make `admin` an ordinary verb.
ADMIN_OVERRIDE = RolePermission.ValidPermissions.ADMIN.value


async def principal(request: Request) -> User:
    return request.scope["user"]


Principal = Annotated[User, Depends(principal)]


async def auth(request: Request) -> set[str]:
    return request.scope["auth"]


Auth = Annotated[set[str], Depends(auth)]


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
                request.scope["auth"] = await user.awaitable_attrs.global_permissions
                request.scope["user"] = user
                return
        except (jwt.InvalidSignatureError, jwt.ExpiredSignatureError, jwt.DecodeError):
            pass
    request.scope["auth"] = set()
    request.scope["user"] = None


async def check_authorization(request: Request):
    endpoint = request.scope["route"].endpoint

    if not getattr(endpoint, "is_public", False) and request.scope.get("user") is None:
        raise ForbiddenException()

    required = getattr(endpoint, "required_permissions", None)
    if required:
        held = request.scope.get("auth") or set()
        if ADMIN_OVERRIDE not in held and required.isdisjoint(held):
            raise ForbiddenException()
