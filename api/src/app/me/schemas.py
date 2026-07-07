from typing import Annotated

from annotated_types import Len
from pydantic import BaseModel

from app.models import User

Password = Annotated[str, Len(min_length=User.MIN_PASSWORD_LENGTH)]


class UserOutput(BaseModel):
    id: int
    username: str
    avatar: str
