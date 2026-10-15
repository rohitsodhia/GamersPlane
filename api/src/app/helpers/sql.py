from collections.abc import Collection

from sqlalchemy import ColumnElement, any_, bindparam
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import InstrumentedAttribute


def in_array(column: InstrumentedAttribute, values: Collection) -> ColumnElement[bool]:
    """``column = ANY(:values)``: like ``column.in_(values)``, but the list goes
    to Postgres as one array parameter rather than one parameter per item, which
    matters for lists of thousands of ids."""
    return column == any_(bindparam(None, list(values), type_=ARRAY(column.type)))
