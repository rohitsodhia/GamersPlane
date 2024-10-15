from typing import Optional


class ValidationError(Exception):
    def __init__(self, message: Optional[str] = None) -> None:
        if not message:
            message = "Validation error"
        super().__init__(message)
