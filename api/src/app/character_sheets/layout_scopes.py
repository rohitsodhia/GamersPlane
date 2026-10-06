"""The value scopes of a sheet layout -- mirrors the frontend's `scope-keys.ts`.

A scope is the sheet root, one repeater row template, or one grid row. Its
fields are the value-bearing nodes reachable without crossing into a nested
repeater's or grid's rows: a `repeater` / `grid` is itself a field of the
enclosing scope (it owns one array / object there), but its row fields belong
to the row's own scope.

Each scope maps a field's `name` (what refs use) to the field, which carries
its `id` (the value-store key; the name when there's no id, like the
renderer). Duplicate names aren't rejected; like the renderer, the first one
wins.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SCALAR_FIELD_TYPES = frozenset({"input", "textarea", "select", "checkbox"})

type Scope = dict[str, Field]


@dataclass(frozen=True)
class GridRow:
    id: str
    scope: Scope


@dataclass(frozen=True)
class Field:
    kind: Literal["value", "repeater", "grid"]
    id: str
    # The node's `type` (`input`, `select`, `text`, `repeater`, ...).
    element_type: str
    # Repeater only: the scope each row's fields live in.
    row_scope: Scope | None = None
    # Grid only: row key -> that row.
    rows: dict[str, GridRow] | None = None
    # Select only: its non-blank option values.
    options: tuple[str, ...] | None = None


def scope_for(nodes: object) -> Scope:
    """The `name` -> field map for the scope whose top-level nodes are `nodes`."""
    scope: Scope = {}
    _collect(nodes, scope)
    return scope


def _collect(nodes: object, scope: Scope) -> None:
    for node in dicts(nodes):
        name = node.get("name")
        if isinstance(name, str) and name not in scope:
            field = _field_for(node, name)
            if field is not None:
                scope[name] = field
        for children in _same_scope_children(node):
            _collect(children, scope)


def _field_for(node: dict, name: str) -> Field | None:
    node_type = node.get("type")
    node_id = _id_or(node, name)
    if node_type == "select":
        return Field("value", node_id, node_type, options=_select_options(node))
    if node_type in SCALAR_FIELD_TYPES:
        return Field("value", node_id, node_type)
    if node_type == "text" and node.get("formula") is not None:
        return Field("value", node_id, node_type)
    if node_type == "repeater":
        return Field(
            "repeater", node_id, node_type, row_scope=scope_for(node.get("content"))
        )
    if node_type == "grid":
        return Field("grid", node_id, node_type, rows=_grid_rows(node))
    return None


def _select_options(node: dict) -> tuple[str, ...]:
    """A select's option values: a bare string, or a `{value, label}`'s
    `value`. Blank ones are left out."""
    options = node.get("values")
    values = (
        option.get("value") if isinstance(option, dict) else option
        for option in (options if isinstance(options, list) else [])
    )
    return tuple(value for value in values if isinstance(value, str) and value)


def _grid_rows(node: dict) -> dict[str, GridRow]:
    """A grid's rows, keyed by their author-facing `key`, in either authoring
    form. A repeated key: the last one wins, like the renderer."""
    rows: dict[str, GridRow] = {}
    items = node.get("items")
    if items is not None:
        row_scope = scope_for(node.get("row"))
        for item in dicts(items):
            if isinstance(item.get("key"), str):
                rows[item["key"]] = GridRow(_id_or(item, item["key"]), row_scope)
        return rows
    for child in dicts(node.get("content")):
        if child.get("type") == "grid_row" and isinstance(child.get("key"), str):
            rows[child["key"]] = GridRow(
                _id_or(child, child["key"]), scope_for(child.get("content"))
            )
    return rows


def _id_or(node: dict, fallback: str) -> str:
    node_id = node.get("id")
    return node_id if isinstance(node_id, str) and node_id else fallback


def _same_scope_children(node: dict) -> list[object]:
    """Child lists rendered in the same value scope as `node` (a repeater's or
    grid's rows are their own scopes; only headers stay in this one)."""
    node_type = node.get("type")
    if node_type == "repeater":
        return [node.get("header")]
    if node_type == "grid":
        headers = [
            child.get("content")
            for child in dicts(node.get("content"))
            if child.get("type") == "grid_header"
        ]
        return [node.get("header"), *headers]
    return [node.get("content")]


def dicts(nodes: object) -> list[dict]:
    return [n for n in nodes if isinstance(n, dict)] if isinstance(nodes, list) else []
