"""Save-time check that a character's values only use keys its sheet knows.

The values document is keyed by field id, scope by scope (see
`layout_scopes.py`), the way the frontend renderer writes it:

- a scalar field: `<field id>: <value>`
- a repeater: `<repeater id>: [{<field id>: <value>, ...}, ...]`, one object
  per row
- a grid: `<grid id>: {<row id>: {<field id>: <value>, ...}, ...}`

Every key must be a field (or grid row) of the character's pinned sheet
version, in the scope it appears in -- or already be stored at that spot on
the character. Those orphans are values for fields a later sheet version
removed; they're kept (unchecked) so an upgrade can offer to carry them over.
A repeater's rows are index-aligned but can be reordered by removals, so a
key stored in any of its rows counts for all of them.

Only keys and the containers' shapes are checked, not the values themselves.
"""

from __future__ import annotations

from app.character_sheets.layout_scopes import Field, Scope, scope_for
from app.exceptions import ValidationError

# The keys already stored at one spot in the values document, each with the
# keys stored under it (a repeater's rows merged into one).
type _Stored = dict[str, _Stored]


def validate_character_values(values: dict, layout: dict, stored: dict | None) -> None:
    """Raise ``ValidationError`` on the first key in `values` that `layout`
    doesn't define and `stored` (the character's current values) doesn't
    already hold."""
    _check_scope(
        values,
        scope_for(layout.get("elements")),
        _stored_keys(stored),
        path="values",
    )


def _stored_keys(value: object) -> _Stored:
    if isinstance(value, dict):
        return {key: _stored_keys(child) for key, child in value.items()}
    if isinstance(value, list):
        merged: _Stored = {}
        for row in value:
            _merge(merged, _stored_keys(row))
        return merged
    return {}


def _merge(into: _Stored, other: _Stored) -> None:
    for key, children in other.items():
        _merge(into.setdefault(key, {}), children)


def _check_scope(values: dict, scope: Scope, stored: _Stored, *, path: str) -> None:
    fields = {field.id: field for field in scope.values()}
    for key, value in values.items():
        field = fields.get(key)
        if field is None:
            if key in stored:
                continue
            raise ValidationError(f"Unknown field id '{key}' in {path}")
        _check_field(field, value, stored.get(key, {}), path=f"{path}.{key}")


def _check_field(field: Field, value: object, stored: _Stored, *, path: str) -> None:
    if field.kind == "value" or value is None:
        return

    if field.kind == "repeater":
        if not isinstance(value, list):
            raise ValidationError(f"{path} must be a list of rows")
        for index, row in enumerate(value):
            if row is None:
                continue
            if not isinstance(row, dict):
                raise ValidationError(f"{path}[{index}] must be an object")
            _check_scope(row, field.row_scope or {}, stored, path=f"{path}[{index}]")
        return

    if not isinstance(value, dict):
        raise ValidationError(f"{path} must be an object of rows")
    rows = {row.id: row for row in (field.rows or {}).values()}
    for row_id, row_values in value.items():
        row = rows.get(row_id)
        if row is None:
            if row_id in stored:
                continue
            raise ValidationError(f"Unknown grid row id '{row_id}' in {path}")
        if row_values is None:
            continue
        if not isinstance(row_values, dict):
            raise ValidationError(f"{path}.{row_id} must be an object")
        _check_scope(
            row_values, row.scope, stored.get(row_id, {}), path=f"{path}.{row_id}"
        )
