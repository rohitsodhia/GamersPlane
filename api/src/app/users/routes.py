from fastapi import APIRouter, status
from sqlalchemy import select

from app.database import DBSessionDependency
from app.helpers.decorators import public
from app.helpers.functions import error_response
from app.models import User
from app.users import schemas

users = APIRouter(prefix="/users")


@users.get(
    "/{id}",
    response_model=schemas.GetUserResponse,
)
@public
async def get_user(id: int, db_session: DBSessionDependency):
    user = await db_session.scalar(select(User).where(User.id == id).limit(1))
    if not user:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND, content={"noUser": True}
        )
    response = {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "joinDate": user.join_date,
            "lastActivity": user.last_activity,
        }
    }
    return response
