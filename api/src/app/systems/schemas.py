from app.schema_base import SchemaBase


class PublisherSchema(SchemaBase):
    name: str
    website: str | None


class BasicsSchema(SchemaBase):
    label: str
    url: str


class SystemSchema(SchemaBase):
    id: str
    name: str
    sort_name: str
    publisher: PublisherSchema | None = None
    genres: list[str] = []
    basics: list[BasicsSchema] = []
    has_char_sheet: bool
    enabled: bool


class GetSystemsResponse(SchemaBase):
    systems: list[SystemSchema]


class BasicSystemSchema(SchemaBase):
    id: str
    name: str
    sort_name: str
    genres: list[str] = []
    has_char_sheet: bool


class GetBasicSystemsResponse(SchemaBase):
    systems: list[BasicSystemSchema]
