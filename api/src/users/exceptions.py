class UserExists(Exception):
    def __init__(self) -> None:
        super().__init__("User already exists")
