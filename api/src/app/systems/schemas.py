from pydantic import BaseModel


class PublisherSchema(BaseModel):
    name: str
    website: str | None


class BasicsSchema(BaseModel):
    label: str
    url: str


class SystemSchema(BaseModel):
    id: str
    name: str
    sort_name: str
    publisher: PublisherSchema | None = None
    genres: list[str] = []
    basics: list[BasicsSchema] = []
    has_char_sheet: bool
    enabled: bool


class GetSystemsResponse(BaseModel):
    systems: list[SystemSchema]


class BasicSystemSchema(BaseModel):
    id: str
    name: str
    sort_name: str
    genres: list[str] = []
    has_char_sheet: bool


class GetBasicSystemsResponse(BaseModel):
    systems: list[BasicSystemSchema]
