class NotFoundException(Exception):
    def __init__(self, message: str | None = None) -> None:
        if not message:
            message = "Not found"
        super().__init__(message)


class ForbiddenException(Exception):
    def __init__(self, message: str | None = None) -> None:
        if not message:
            message = "Forbidden"
        super().__init__(message)


class ValidationError(Exception):
    def __init__(self, message: str | None = None) -> None:
        if not message:
            message = "Validation error"
        super().__init__(message)
