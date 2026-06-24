from app.schemas import ErrorItem


class UserExists(Exception):
    def __init__(self, errors: list[ErrorItem]) -> None:
        super().__init__("User already exists")
        self.errors = errors
