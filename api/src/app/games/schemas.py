from __future__ import annotations

import datetime

from app.models import Game
from app.schema_base import SchemaBase, filtered_str


class NewGameInput(SchemaBase):
    title: str = filtered_str()
    system_id: str
    allowed_char_sheets: list[str]
    start: datetime.datetime
    end: datetime.datetime | None
    post_frequency: str
    num_players: int
    chars_per_player: int
    description: dict | None
    char_gen_info: dict | None
    status: Game.Statuses
    public: bool


class NewGameResponse(SchemaBase):
    id: int
