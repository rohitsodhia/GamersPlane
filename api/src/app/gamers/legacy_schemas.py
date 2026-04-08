from pydantic import BaseModel


class User(BaseModel):
    id: int
    username: str
    online: bool
    avatar: str
    lfg: bool
    inactive: bool


class GetGamersResponse(BaseModel):
    gamers: list[User]
