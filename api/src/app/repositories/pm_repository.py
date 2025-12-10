from __future__ import annotations

from typing import Literal


class PMRepository:
    def __init__(self, db_session):
        self.db_session = db_session

    async def get_pm_count(
        self, user_id: int, box: Literal["inbox", "outbox"] = "inbox"
    ) -> int | None:
        pass

    async def get_pms(
        self, user_id: int, box: Literal["inbox", "outbox"] = "inbox", page: int = 1
    ) -> int | None:
        if page < 1:
            page = 1
