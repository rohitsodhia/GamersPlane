import os
import jwt

from fastapi import Request
from asgiref.sync import sync_to_async

import envs
from globals import g

from users.models import User


async def validate_jwt(request: Request, call_next):
    g.current_user = None

    token = request.headers.get("Authorization")
    if token and token[:7] == "Bearer ":
        token = token[7:]
        try:
            jwt_body = jwt.decode(
                token,
                envs.JWT_SECRET_KEY,
                algorithms=envs.JWT_ALGORITHM,
            )
        except jwt.ExpiredSignatureError:
            return await call_next(request)

    try:
        g.current_user = await sync_to_async(User.objects.get)(id=jwt_body["user_id"])
    except User.DoesNotExist:
        pass

    response = await call_next(request)
    return response
