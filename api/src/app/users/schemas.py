from datetime import datetime

from app.schema_base import SchemaBase


class ActiveGameData(SchemaBase):
    id: int
    name: str
    isGM: bool
    system: str
    forumId: int | None


class SystemData(SchemaBase):
    id: str
    name: str


class SystemCountData(SchemaBase):
    system: SystemData
    count: int


class SystemsCountData(SchemaBase):
    count: int
    systems: list[SystemCountData]


class UserDict(SchemaBase):
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


class GetUserResponse(SchemaBase):
    user: UserDict


class SearchUserDict(SchemaBase):
    id: int
    username: str


class SearchUserResponse(SchemaBase):
    user: SearchUserDict
