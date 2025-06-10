from pydantic import BaseModel


class ErrorResponse[ErrorT: BaseModel](BaseModel):
    error: ErrorT
