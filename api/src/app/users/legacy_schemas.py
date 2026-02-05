from pydantic import BaseModel


class HeaderCharacters(BaseModel):
    id: int
    isFavorite: bool
    label: str
    system: str


class GetHeaderResponse(BaseModel):
    characters: list[HeaderCharacters]
