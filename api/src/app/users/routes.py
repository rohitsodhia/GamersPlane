from fastapi import APIRouter, status
from sqlalchemy import select

from app.database import DBSessionDependency
from app.helpers.decorators import public
from app.helpers.functions import error_response
from app.models import User
from app.repositories import UserRepository
from app.schemas import ErrorItem
from app.users import schemas

users = APIRouter(prefix="/users")


@users.get(
    "/search",
    response_model=schemas.SearchUserResponse,
)
async def search_user(username: str, db_session: DBSessionDependency):
    user_repository = UserRepository(db_session)

    user = await user_repository.search_by_username(username)
    if not user:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            errors=[ErrorItem(code="user_not_found", detail="User not found")],
        )
    response = {
        "user": {
            "id": user.id,
            "username": user.username,
        }
    }
    return response


@users.get(
    "/{id}",
    response_model=schemas.GetUserResponse,
)
@public
async def get_user(id: int, db_session: DBSessionDependency):
    user = await db_session.scalar(select(User).where(User.id == id).limit(1))
    if not user:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            errors=[ErrorItem(code="user_not_found", detail="User not found")],
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
