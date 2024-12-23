from datetime import datetime
from typing import Dict, List

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


class GetUserResponse(BaseModel):
    user: UserDict
