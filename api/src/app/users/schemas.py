from datetime import datetime

from pydantic import BaseModel


class UserDict(BaseModel):
    id: int
    username: str
    avatar: str
    joinDate: datetime
    lastActivity: datetime | None = None
    pronouns: str | None
    showAge: bool = False
    age: str | None
    location: str | None
    postCount: int
    communityPostCount: int
    gamePostCount: int


class GetUserResponse(BaseModel):
    user: UserDict


class SearchUserDict(BaseModel):
    id: int
    username: str


class SearchUserResponse(BaseModel):
    user: SearchUserDict
