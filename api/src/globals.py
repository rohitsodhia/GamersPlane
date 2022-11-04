import os
from typing import Any


class globals:
    def __setattr__(self, __name: str, __value: Any) -> None:
        object.__setattr__(self, __name, __value)


g = globals()

PAGINATE_PER_PAGE: int = os.getenv("PAGINATE_PER_PAGE")
