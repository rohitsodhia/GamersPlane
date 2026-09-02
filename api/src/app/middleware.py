from typing import Annotated

import jwt
from fastapi import Depends, Request

from app.configs import configs
from app.database import DBSessionDependency
from app.exceptions import BannedException, ForbiddenException, SuspendedException
from app.models import RolePermission, User
from app.repositories.user_repository import UserRepository

# Global superuser verb: holding it satisfies any @requires check. Delete this
# constant and the guard in check_authorization to make `admin` an ordinary verb.
ADMIN_OVERRIDE = RolePermission.ValidPermissions.ADMIN.value


async def principal(request: Request) -> User:
    return request.scope["user"]


Principal = Annotated[User, Depends(principal)]


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
            # Identity only — a banned/suspended user is still resolved here so
            # check_authorization can reject them with a specific reason.
            if user:
                await user_repository.update_last_activity(user)
                request.scope["auth"] = await user.awaitable_attrs.global_permissions
                request.scope["user"] = user
                return
        except (jwt.InvalidSignatureError, jwt.ExpiredSignatureError, jwt.DecodeError):
            pass
    request.scope["auth"] = set()
    request.scope["user"] = None


def enforce_login_eligibility(user: User) -> None:
    """Raise a specific exception if the user may not hold an authed session.

    Shared by ``/auth/login`` (before issuing a JWT) and ``check_authorization``
    (on every authenticated request, so a ban lands before the 2-week JWT lapses).
    """
    block = user.login_block()
    if block == "banned":
        raise BannedException()
    if block == "suspended":
        raise SuspendedException(user.suspended_until)


async def check_authorization(request: Request):
    endpoint = request.scope["route"].endpoint

    if not getattr(endpoint, "is_public", False):
        user = request.scope.get("user")
        if user is None:
            raise ForbiddenException()
        enforce_login_eligibility(user)

    required = getattr(endpoint, "required_permissions", None)
    if required:
        held = request.scope.get("auth") or set()
        if ADMIN_OVERRIDE not in held and required.isdisjoint(held):
            raise ForbiddenException()
