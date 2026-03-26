from pydantic import BaseModel


class PublisherSchema(BaseModel):
    name: str
    website: str | None = None


class SystemSchema(BaseModel):
    id: str
    name: str
    sort_name: str
    publisher: PublisherSchema | None = None
    genres: list[str] = []
    basics: list | None = None
    has_char_sheet: bool
    lfg: int
    enabled: bool
    angular: bool


class GetSystemsResponse(BaseModel):
    systems: list[SystemSchema]
