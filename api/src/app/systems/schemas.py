from pydantic import BaseModel


class PublisherSchema(BaseModel):
    name: str
    website: str | None


class SystemSchema(BaseModel):
    id: str
    name: str
    sort_name: str
    publisher: PublisherSchema | None = None
    genres: list[str] = []
    basics: list[dict] = []
    has_char_sheet: bool
    enabled: bool


class GetSystemsResponse(BaseModel):
    systems: list[SystemSchema]
