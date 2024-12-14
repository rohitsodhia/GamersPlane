class UserExists(Exception):
    def __init__(self, errors: dict) -> None:
        super().__init__("User already exists")
        self.errors = errors
