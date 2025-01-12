from pydantic import BaseModel


class PublisherSchema(BaseModel):
    name: str
    website: str


class SystemSchema(BaseModel):
    id: str
    name: str
    sortName: str
    publisher: PublisherSchema | None = None
    genres: list[str] = []
    basics: dict | None = None
    hasCharSheet: bool
    enabled: bool


class GetSystemsResponse(BaseModel):
    systems: list[SystemSchema]
