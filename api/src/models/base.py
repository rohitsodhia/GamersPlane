from datetime import datetime
from typing import Optional

from sqlalchemy import event, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, with_loader_criteria

from database import session


class Base(DeclarativeBase):
    pass


class SoftDeleteMixin:
    deleted: Mapped[Optional[datetime]] = mapped_column(default=None)


@event.listens_for(session, "do_orm_execute")
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
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.now(), onupdate=func.current_timestamp()
    )
