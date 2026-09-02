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


class BannedException(Exception):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or "This account has been banned")


class SuspendedException(Exception):
    def __init__(self, suspended_until=None) -> None:
        if suspended_until is not None:
            message = (
                f"This account is suspended until "
                f"{suspended_until:%Y-%m-%d %H:%M UTC}"
            )
        else:
            message = "This account is suspended"
        super().__init__(message)


class ValidationError(Exception):
    def __init__(self, message: str | None = None) -> None:
        if not message:
            message = "Validation error"
        super().__init__(message)


class ConflictException(Exception):
    def __init__(self, message: str | None = None) -> None:
        if not message:
            message = "Conflict"
        super().__init__(message)
