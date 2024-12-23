class ValidationError(Exception):
    def __init__(self, message: str | None = None) -> None:
        if not message:
            message = "Validation error"
        super().__init__(message)
