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
    activated: bool = True
    banned: datetime | None = None
    # Everything below is "full" data: populated by GET /users/{id} always, and by
    # GET /users only when full=true. Optional so response_model_exclude_none can
    # omit it on the lightweight list rows.
    pronouns: str | None = None
    showAge: bool = False
    age: str | None = None
    location: str | None = None
    postCount: int | None = None
    communityPostCount: int | None = None
    gamePostCount: int | None = None
    activeGames: list[ActiveGameData] | None = None
    characters: SystemsCountData | None = None
    gmStats: SystemsCountData | None = None


class GetUserResponse(SchemaBase):
    user: UserDict


class SearchUserDict(SchemaBase):
    id: int
    username: str


class SearchUserResponse(SchemaBase):
    user: SearchUserDict


class SearchUsersResponse(SchemaBase):
    users: list[SearchUserDict]


class GetUsersResponse(SchemaBase):
    users: list[UserDict]
    count: int
    page: int


class BanUserResponse(SchemaBase):
    banned: datetime | None
