from typing import List, Dict
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserDict(BaseModel):
    username: str
    email: EmailStr
    joinDate: datetime
    lastActivity: datetime
    suspendedUntil: datetime
    banned: bool
    roles: List[str]
    permissions: Dict
    admin: bool


class GetUserResponse(BaseModel):
    user: UserDict
