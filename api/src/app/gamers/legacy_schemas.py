from pydantic import BaseModel


class User(BaseModel):
    id: int
    username: str
    online: bool
    avatar: str
    inactive: bool


class GetGamersResponse(BaseModel):
    gamers: list[User]
