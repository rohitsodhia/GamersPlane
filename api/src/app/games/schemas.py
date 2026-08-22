from __future__ import annotations

from app.schema_base import SchemaBase, filtered_str


class NewGameInput(SchemaBase):
    title: str = filtered_str()
    system_id: str
    allowed_char_sheets: list[str]
    post_frequency: str
    num_players: int
    chars_per_player: int
    description: dict | None
    char_gen_info: dict | None
    public: bool
    recruitment_thread_id: int | None
    advanced_options: dict | None


class NewGameResponse(SchemaBase):
    id: int
