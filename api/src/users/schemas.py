from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserDict(BaseModel):
    id: int
    username: str
    email: EmailStr
    joinDate: datetime
    lastActivity: Optional[datetime] = None


class GetUserResponse(BaseModel):
    user: UserDict
