from os import error

from fastapi import APIRouter, status

from helpers.functions import error_response
from models import User
from users import schemas

users = APIRouter(prefix="/users")


@users.get(
    "/{id}",
    response_model=schemas.GetUserResponse,
)
def get_user(id: int):
    try:
        user = User.objects.get(id=id)
    except User.DoesNotExist:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND, content={"noUser": True}
        )
    return {"user": user.to_dict()}
