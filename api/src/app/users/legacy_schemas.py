from pydantic import BaseModel


class HeaderCharacters(BaseModel):
    id: int
    isFavorite: bool
    label: str
    system: str


class HeaderGames(BaseModel):
    gameID: int
    title: str
    forumID: int
    retired: bool
    isGM: bool
    isPlayer: bool
    isFavorite: bool


class GetHeaderResponse(BaseModel):
    characters: list[HeaderCharacters]
    games: list[HeaderGames]
