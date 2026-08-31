from app.schema_base import SchemaBase


class ErrorItem(SchemaBase):
    field: str | None = None
    code: str
    detail: str
