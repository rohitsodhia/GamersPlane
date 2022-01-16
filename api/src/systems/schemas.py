from typing import List, Dict

from pydantic import BaseModel


class PublisherSchema(BaseModel):
    name: str
    website: str


class SystemSchema(BaseModel):
    id: str
    name: str
    sortName: str
    publisher: PublisherSchema = None
    genres: List[str] = []
    basics: Dict = None
    hasCharSheet: bool
    enabled: bool


class GetSystemsResponse(BaseModel):
    systems: List[SystemSchema]
