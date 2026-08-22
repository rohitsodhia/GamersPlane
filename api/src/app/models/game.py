from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.enums import LabelEnum, LabelEnumType
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models import Forum, Role, System, User

POST_FREQUENCY_PATTERN = re.compile(r"^([1-9]\d?)/([dw])$")


@dataclass(frozen=True)
class PostFrequency:
    times_per: int
    per_period: Literal["d", "w"]

    def __str__(self) -> str:
        return f"{self.times_per}/{self.per_period}"


class Game(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "games"

    class Statuses(LabelEnum):
        OPEN = True, "Open"
        CLOSED = False, "Closed"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50))
    system_id: Mapped[str] = mapped_column(ForeignKey("systems.id"))
    system: Mapped[System] = relationship()
    allowed_char_sheets: Mapped[list[System]] = relationship(
        secondary="game_allowed_systems"
    )
    gm_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    gm: Mapped[User] = relationship()
    created: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )
    start: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )
    end: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    _post_frequency: Mapped[str] = mapped_column("post_frequency", String(4))
    num_players: Mapped[int] = mapped_column()
    chars_per_player: Mapped[int] = mapped_column(default=1)
    description: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    char_gen_info: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    root_forum_id: Mapped[int] = mapped_column(ForeignKey("forums.id"))
    root_forum: Mapped[Forum] = relationship(foreign_keys=[root_forum_id])
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    role: Mapped[Role] = relationship()
    status: Mapped[Statuses] = mapped_column(
        LabelEnumType(Statuses, Boolean), default=Statuses.OPEN
    )
    public: Mapped[bool] = mapped_column()
    recruitment_thread_id: Mapped[int | None] = mapped_column(nullable=True)
    advanced_options: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    retired: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    @property
    def post_frequency(self) -> PostFrequency:
        match = POST_FREQUENCY_PATTERN.match(self._post_frequency)
        if not match:
            raise ValueError(
                f"invalid post_frequency in database: {self._post_frequency!r}"
            )
        per_period = cast(Literal["d", "w"], match.group(2))
        return PostFrequency(int(match.group(1)), per_period)

    @post_frequency.setter
    def post_frequency(self, value: PostFrequency | str) -> None:
        value = str(value)
        if not POST_FREQUENCY_PATTERN.match(value):
            raise ValueError(
                f"post_frequency must match ##/[dw] (e.g. '3/w'), got {value!r}"
            )
        self._post_frequency = value
