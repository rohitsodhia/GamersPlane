from fastapi import APIRouter

from app.configs import configs
from app.me import schemas
from app.middleware import AuthedUser

auth = APIRouter(prefix="/me")


@auth.get("", response_model=schemas.UserOutput)
async def get_current_user(current_user: AuthedUser):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "avatar": f"{configs.AVATARS_ROOT}/{current_user.avatar}",
    }
