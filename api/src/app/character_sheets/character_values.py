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

import copy

from app.character_sheets.layout_ids import collect_ids, field_labels
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


def set_live_value(
    values: dict | None, layout: dict, path: list[str | int], value: object
) -> dict:
    """A copy of `values` with `value` written at `path`, after checking that
    `path` addresses a `live: true` field of `layout` and that `value` suits it.

    `path` is the field's address in the values document: field ids, with a
    repeater's row index (int) or a grid's row id (str) after each repeater /
    grid id. Containers missing along the way are created, except that a
    repeater row must already exist: a live write never adds rows.
    """
    field = _live_field(layout, path)
    _check_live_value(field, value)

    updated = copy.deepcopy(values) if values else {}
    node: dict | list = updated
    for index, segment in enumerate(path[:-1]):
        if isinstance(segment, int):
            if not isinstance(node, list) or not 0 <= segment < len(node):
                raise ValidationError("That repeater row doesn't exist")
            if not isinstance(node[segment], dict):
                node[segment] = {}
            node = node[segment]
            continue
        if not isinstance(node, dict):
            raise ValidationError("Field path doesn't match the stored values")
        child = node.get(segment)
        if not isinstance(child, dict | list):
            child = [] if isinstance(path[index + 1], int) else {}
            node[segment] = child
        node = child
    if not isinstance(node, dict):
        raise ValidationError("Field path doesn't match the stored values")
    node[path[-1]] = value

    return updated


def _live_field(layout: dict, path: list[str | int]) -> Field:
    """Walk `layout` along `path` to the live scalar field it names."""
    scope = scope_for(layout.get("elements"))
    position = 0
    while position < len(path):
        segment = path[position]
        field = (
            next((f for f in scope.values() if f.id == segment), None)
            if isinstance(segment, str)
            else None
        )
        if field is None:
            raise ValidationError(f"Unknown field '{segment}' in the field path")
        position += 1

        if field.kind == "value":
            if position != len(path):
                raise ValidationError("Field path continues past a value field")
            if not field.live:
                raise ValidationError(f"Field '{segment}' isn't live")
            return field

        if position >= len(path):
            raise ValidationError(f"Field path ends at the container '{segment}'")
        coordinate = path[position]
        position += 1
        if field.kind == "repeater":
            if not isinstance(coordinate, int) or isinstance(coordinate, bool):
                raise ValidationError(f"'{segment}' needs a row index")
            scope = field.row_scope or {}
        else:
            row = next(
                (r for r in (field.rows or {}).values() if r.id == coordinate), None
            )
            if row is None:
                raise ValidationError(f"Unknown grid row '{coordinate}' in '{segment}'")
            scope = row.scope
    # Only reached after a row coordinate with no field after it (the loop
    # returns on the first value field, and `path` is never empty).
    raise ValidationError("Field path ends at the container, not a field")


def _check_live_value(field: Field, value: object) -> None:
    if field.element_type == "checkbox":
        valid = isinstance(value, bool)
    elif field.element_type == "select":
        valid = isinstance(value, str) and (value == "" or value in field.options)
    else:
        # input and textarea: text, or a number typed into a numeric input.
        valid = isinstance(value, str) or (
            isinstance(value, int | float) and not isinstance(value, bool)
        )
    if not valid:
        raise ValidationError(f"Invalid value for a {field.element_type} field")


def character_name(values: dict | None, layout: dict) -> str | None:
    """The value of the sheet's required root `name` field, or None if it's
    blank. Copied onto `Character.name` whenever values or the pinned layout
    change, so readers don't have to walk the layout."""
    field = scope_for(layout.get("elements")).get("name")
    if field is None or not values:
        return None
    value = values.get(field.id)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def hidden_values(
    values: dict | None, current_layout: dict, target_layout: dict
) -> list[tuple[str, str]]:
    """The `(id, label)` of each field the character has a value for in
    `current_layout` that `target_layout` doesn't have, by label: what a move
    to `target_layout` would stop showing. The values themselves stay stored.

    Ids are unique across a whole layout, so they're matched wherever they
    sit. A missing repeater or grid is reported on its own, not field by field.
    Values stored for neither layout were already hidden, so they're left out.
    """
    labels = field_labels(current_layout)
    target_ids = collect_ids(target_layout)
    hidden: dict[str, str] = {}

    def walk(value: object) -> None:
        if isinstance(value, list):
            for row in value:
                walk(row)
        if not isinstance(value, dict):
            return
        for key, child in value.items():
            if key in labels and key not in target_ids:
                if child not in (None, "", [], {}):
                    hidden[key] = labels[key]
                continue
            walk(child)

    walk(values)
    return sorted(hidden.items(), key=lambda field: field[1])


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
