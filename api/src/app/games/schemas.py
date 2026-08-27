from __future__ import annotations

import datetime
from typing import Literal

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


class GameIdResponse(SchemaBase):
    id: int


class UserData(SchemaBase):
    id: int
    username: str


class PostFrequencyData(SchemaBase):
    times_per: int
    per_period: Literal["d", "w"]


PlayerState = Literal["invited", "applied", "accepted"]


class PlayerData(SchemaBase):
    id: int
    username: str
    is_gm: bool
    state: PlayerState


class GetGameResponse(SchemaBase):
    id: int
    title: str
    system: str
    allowed_char_sheets: list[str]
    gm: UserData
    created: datetime.datetime
    end: datetime.datetime | None
    post_frequency: PostFrequencyData
    num_players: int
    chars_per_player: int
    description: dict | None
    char_gen_info: dict | None
    root_forum_id: int
    status: Literal["open", "closed"]
    public: bool
    recruitment_thread_id: int | None
    advanced_options: dict | None
    retired: datetime.datetime | None
    players: list[PlayerData]
    viewer_state: PlayerState | None
    favorited: bool


class GameData(SchemaBase):
    id: int
    title: str
    system: str
    gm: UserData
    post_frequency: PostFrequencyData
    num_players: int
    player_count: int
    forum_id: int
    is_gm: bool
    is_retired: bool
    status: Literal["open", "closed"]
    favorited: bool


class GetGamesResponse(SchemaBase):
    games: list[GameData]


class FavoriteGameResponse(SchemaBase):
    favorite: bool


class InvitePlayerInput(SchemaBase):
    username: str


class UpdateGameInput(SchemaBase):
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


class DeckData(SchemaBase):
    id: int
    label: str
    type: str
    size: int
    position: int
    permissions: list[int]


class GetDecksResponse(SchemaBase):
    decks: list[DeckData]


class GetDeckResponse(SchemaBase):
    deck: DeckData


class CreateDecksInput(SchemaBase):
    label: str
    type: str
    permissions: list[int]


class CreateDecksResponse(SchemaBase):
    id: int
