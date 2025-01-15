import envs
import jwt
from database import DBSessionDependency
from fastapi import HTTPException, Request, status
from models import User
from repositories.user_repository import UserRepository


async def validate_jwt(request: Request, db_session: DBSessionDependency):
    token = request.headers.get("Authorization")
    request.scope["auth"] = None
    request.scope["user"] = None
    if token and token[:7] == "Bearer ":
        token = token[7:]
        try:
            jwt_body = jwt.decode(
                token,
                envs.JWT_SECRET_KEY,
                algorithms=[envs.JWT_ALGORITHM],
            )
            user_repo = UserRepository(db_session)
            user = await user_repo.get_user(jwt_body["user_id"])
            if user:
                request.scope["auth"] = await user.awaitable_attrs.permissions
                request.scope["user"] = user
        except:
            pass


async def check_authorization(request: Request):
    public = getattr(request.scope["route"].endpoint, "is_public", False)

    if not public:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
