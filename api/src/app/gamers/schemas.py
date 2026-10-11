from datetime import datetime

from app.schema_base import SchemaBase


class Gamer(SchemaBase):
    id: int
    username: str
    avatar: str
    online: bool
    lfg: bool
    lastActivity: datetime | None = None


class GetGamersResponse(SchemaBase):
    gamers: list[Gamer]
    total: int
