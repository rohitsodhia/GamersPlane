import jwt
from fastapi import HTTPException, Request, status

import envs
import globals
from database import get_db_session
from models import User
from repositories.user_repository import UserRepository


async def validate_jwt(request: Request, call_next):
    db_session = get_db_session()
    globals.current_user = None

    token = request.headers.get("Authorization")
    if token and token[:7] == "Bearer ":
        token = token[7:]
        try:
            jwt_body = jwt.decode(
                token,
                envs.JWT_SECRET_KEY,
                algorithms=[envs.JWT_ALGORITHM],
            )
            globals.current_user = await User.get(jwt_body["user_id"])
        except:
            pass

    response = await call_next(request)
    return response


async def check_authorization(request: Request):
    public = getattr(request.scope["route"].endpoint, "is_public", False)

    if not public:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
