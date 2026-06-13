from datetime import datetime
from typing import Annotated, Any

from annotated_types import Len
from pydantic import BaseModel

from app.models.legacy import User

Password = Annotated[str, Len(min_length=User.MIN_PASSWORD_LENGTH)]


class GetCurrentUserResponse(BaseModel):
    user_id: int
    username: str
    email: str
    joinDate: datetime
    activatedOn: datetime
    usermeta: dict[str, Any]
    acpPermissions: list[str]
