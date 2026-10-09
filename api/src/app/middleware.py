from typing import Annotated

import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.configs import configs
from app.database import DBSessionDependency
from app.exceptions import BannedException, ForbiddenException, SuspendedException
from app.models import Role, RolePermission, User
from app.models.user import global_permissions_of
from app.repositories.user_repository import UserRepository

# Global superuser verb: holding it satisfies any @requires check. Delete this
# constant and the guard in check_authorization to make `admin` an ordinary verb.
ADMIN_OVERRIDE = RolePermission.ValidPermissions.ADMIN.value

# Sent as "1" by the frontend while the user is in moderator mode; absent means
# player mode (see ForumPermissions).
MODERATOR_MODE_HEADER = "X-Moderator-Mode"


async def principal(request: Request) -> User:
    return request.scope["user"]


Principal = Annotated[User, Depends(principal)]


async def load_implicit_roles(
    db_session: AsyncSession, role_id: int
) -> tuple[Role, ...]:
    """The system role every principal of a kind implicitly holds (Registered or
    Guest), with its grants loaded. Empty if the role hasn't been seeded."""
    role = await db_session.scalar(
        select(Role).where(Role.id == role_id).options(selectinload(Role.grants))
    )
    return (role,) if role else ()


async def guest_permissions(db_session: AsyncSession) -> set[str]:
    return global_permissions_of(await load_implicit_roles(db_session, Role.GUEST_ID))


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
                user.implicit_roles = await load_implicit_roles(
                    db_session, Role.REGISTERED_ID
                )
                user.moderator_mode = request.headers.get(MODERATOR_MODE_HEADER) == "1"
                request.scope["auth"] = await user.awaitable_attrs.global_permissions
                request.scope["user"] = user
                return
        except (jwt.InvalidSignatureError, jwt.ExpiredSignatureError, jwt.DecodeError):
            pass
    request.scope["auth"] = await guest_permissions(db_session)
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


async def check_authorization(request: Request, db_session: DBSessionDependency):
    endpoint = request.scope["route"].endpoint
    user = request.scope.get("user")

    if not getattr(endpoint, "is_public", False):
        if user is None:
            raise ForbiddenException()
        enforce_login_eligibility(user)
    elif user is not None and user.login_block():
        # A banned/suspended user's token outlives the ban; on public routes
        # they're a guest rather than keeping their roles' read access.
        request.scope["user"] = None
        request.scope["auth"] = await guest_permissions(db_session)

    required = getattr(endpoint, "required_permissions", None)
    if required:
        held = request.scope.get("auth") or set()
        if ADMIN_OVERRIDE not in held and required.isdisjoint(held):
            raise ForbiddenException()
