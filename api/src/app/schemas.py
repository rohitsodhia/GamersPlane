from pydantic import BaseModel


class ErrorItem(BaseModel):
    field: str | None = None
    code: str
    detail: str
