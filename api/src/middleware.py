import jwt
from asgiref.sync import sync_to_async
from fastapi import Request

import envs
from globals import g
from models import User


async def validate_jwt(request: Request, call_next):
    g.current_user = None

    token = request.headers.get("Authorization")
    if token and token[:7] == "Bearer ":
        token = token[7:]
        try:
            jwt_body = jwt.decode(
                token,
                envs.JWT_SECRET_KEY,
                algorithms=[envs.JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            return await call_next(request)

    try:
        g.current_user = await sync_to_async(User.objects.get)(id=jwt_body["user_id"])
    except:
        pass

    response = await call_next(request)
    return response
