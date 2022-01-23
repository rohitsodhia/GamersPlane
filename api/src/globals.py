from typing import Any


class globals:
    def __setattr__(self, __name: str, __value: Any) -> None:
        object.__setattr__(self, __name, __value)


g = globals()
