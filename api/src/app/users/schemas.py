from datetime import datetime

from pydantic import BaseModel


class ActiveGameData(BaseModel):
    id: int
    name: str
    isGM: bool
    system: str
    forumId: int | None


class SystemData(BaseModel):
    id: str
    name: str


class SystemCountData(BaseModel):
    system: SystemData
    count: int


class SystemsCountData(BaseModel):
    count: int
    systems: list[SystemCountData]


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
    activeGames: list[ActiveGameData]
    characters: SystemsCountData
    gmStats: SystemsCountData


class GetUserResponse(BaseModel):
    user: UserDict


class SearchUserDict(BaseModel):
    id: int
    username: str


class SearchUserResponse(BaseModel):
    user: SearchUserDict
