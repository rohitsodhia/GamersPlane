from datetime import datetime

from sqlalchemy import DateTime, event, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    with_loader_criteria,
)


class Base(DeclarativeBase):
    pass


class SoftDeleteMixin:
    deleted: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


@event.listens_for(Session, "do_orm_execute")
def _add_filtering_criteria(execute_state):
    skip_filter = execute_state.execution_options.get("skip_filter", False)
    if execute_state.is_select and not skip_filter:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                SoftDeleteMixin,
                lambda cls: cls.deleted.is_(None),
                include_aliases=True,
            )
        )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.current_timestamp(),
    )
