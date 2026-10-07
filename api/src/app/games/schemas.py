from __future__ import annotations

import datetime
from typing import Annotated, Literal

from annotated_types import Len

from app.schema_base import SchemaBase, filtered_str

# A game must allow at least one character sheet.
AllowedCharSheets = Annotated[list[str], Len(min_length=1)]


class NewGameInput(SchemaBase):
    title: str = filtered_str()
    system_id: str
    allowed_char_sheets: AllowedCharSheets
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


class PlayerCharacterData(SchemaBase):
    id: int
    label: str
    approved: bool


class PlayerData(SchemaBase):
    id: int
    username: str
    is_gm: bool
    state: PlayerState
    characters: list[PlayerCharacterData]


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
    is_retired: bool
    status: Literal["open", "closed"]
    public: bool
    favorited: bool


class MyGameData(GameData):
    is_gm: bool


class GetGamesResponse(SchemaBase):
    games: list[GameData]
    count: int
    page: int


class GetMyGamesResponse(SchemaBase):
    games: list[MyGameData]


class GetLatestGamesResponse(SchemaBase):
    games: list[GameData]


class FavoriteGameResponse(SchemaBase):
    favorite: bool


class InvitePlayerInput(SchemaBase):
    username: str


class SubmitCharacterInput(SchemaBase):
    character_id: int


class UpdateGameInput(SchemaBase):
    title: str = filtered_str()
    system_id: str
    allowed_char_sheets: AllowedCharSheets
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
