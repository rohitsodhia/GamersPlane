"""Server-minted ids for value-bearing sheet nodes.

Step 1 of the sheet-versioning design ([[character_sheet_versioning_and_ids]]
in the assistant's memory, not a code doc): every node that owns a slot in the
value store -- a scalar field (`input`/`textarea`/`select`/`checkbox`/a
computed `text`) or a whole array/object (`repeater`/`grid`), plus a grid's
per-row entries (a compact `items[]` item or an explicit `grid_row`) -- gets a
stable, server-minted `id`. Authors leave `id` blank; :func:`mint_ids` fills it
in on every draft save. Renaming a field's `name` later doesn't orphan it,
because publish tracks the field by `id`, not by name (see
:func:`validate_publish_ids`).

This module does not yet change how *values* are stored or how formula refs
resolve -- both still key off `name`/path (that's step 2, the id-keyed value
store). It only mints and validates the ids themselves.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

from app.exceptions import ValidationError

# Leaf types that always write a scalar under their own `name`.
_SCALAR_FIELD_TYPES = frozenset({"input", "textarea", "select", "checkbox"})

# Container types that write one array/object under their own `name`.
_CONTAINER_FIELD_TYPES = frozenset({"repeater", "grid"})

# Non-repeated child-element keys: nodes here stay in the enclosing scope
# (mirrors `layout_validation._CHILD_ELEMENT_KEYS`, minus `row`, which is a
# *template* and opens its own scope -- handled separately below).
_CHILD_ELEMENT_KEYS = ("content", "header")

# 8 lowercase hex chars -- short, and shaped distinctly from anything a human
# would type by hand in the code editor, so `validate_publish_ids` can reject
# hand-authored ids on new fields without keeping a persistent ledger of every
# id we've ever issued.
_ID_RE = re.compile(r"^[0-9a-f]{8}$")


def _new_id(used: set[str]) -> str:
    while True:
        candidate = secrets.token_hex(4)
        if candidate not in used:
            return candidate


def _field_type(node: dict) -> str | None:
    """The id-bearing "kind" of `node`, or None if it owns no value-store id.

    Both authoring forms of a grid row (a compact `items[]` entry, handled by
    the caller since it isn't a `type`-tagged node, and an explicit
    `grid_row`) are recorded as `"grid_row"` -- switching authoring forms
    shouldn't look like a type change to `validate_publish_ids`.
    """
    node_type = node.get("type")
    if node_type in _SCALAR_FIELD_TYPES or node_type in _CONTAINER_FIELD_TYPES:
        return node_type
    if node_type == "text" and "formula" in node:
        return "text"
    if node_type == "grid_row":
        return "grid_row"
    return None


def _assign_id(node: dict, used: set[str]) -> None:
    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id or node_id in used:
        node_id = _new_id(used)
        node["id"] = node_id
    used.add(node_id)


def mint_ids(layout: dict) -> dict:
    """Fill in a blank/missing/duplicate `id` on every value-bearing node.

    Mutates and returns `layout`. New ids only need to be unique within their
    scope -- the document root (which also covers a grid's `header` and
    explicit `content` rows, since neither is a repeated template), a
    repeater's row template (`content` + `header` together), or a compact
    grid's row template (`row`) -- each tracked with its own `used` set so
    minting one repeater never has to know another repeater's ids.
    """
    _mint_scope(layout.get("elements", []), used=set())
    return layout


def _mint_scope(nodes: object, *, used: set[str]) -> None:
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if isinstance(node, dict):
            _mint_node(node, used=used)


def _mint_node(node: dict, *, used: set[str]) -> None:
    node_type = node.get("type")
    if _field_type(node) is not None:
        _assign_id(node, used)

    if node_type == "repeater":
        row_used: set[str] = set()
        _mint_scope(node.get("content"), used=row_used)
        _mint_scope(node.get("header"), used=row_used)
        return

    if node_type == "grid":
        items = node.get("items")
        if isinstance(items, list):
            item_used: set[str] = set()
            for item in items:
                if isinstance(item, dict):
                    _assign_id(item, item_used)
        _mint_scope(node.get("row"), used=set())
        # `header` (compact) and `content` (explicit grid_header/grid_row)
        # aren't templates -- each node in them is a distinct authored row, so
        # they share the enclosing scope like any other container.
        _mint_scope(node.get("header"), used=used)
        _mint_scope(node.get("content"), used=used)
        return

    for key in _CHILD_ELEMENT_KEYS:
        _mint_scope(node.get(key), used=used)


def collect_ids(layout: object) -> dict[str, list[tuple[str, str]]]:
    """Every id in `layout`, mapped to the `(path, field_type)` of each node
    carrying it -- more than one entry means a duplicate."""
    found: dict[str, list[tuple[str, str]]] = {}
    if isinstance(layout, dict):
        _collect_scope(layout.get("elements"), found, path="elements")
    return found


def _collect_scope(
    nodes: object, found: dict[str, list[tuple[str, str]]], *, path: str
) -> None:
    if not isinstance(nodes, list):
        return
    for index, node in enumerate(nodes):
        if isinstance(node, dict):
            _collect_node(node, found, path=f"{path}[{index}]")


def _collect_node(
    node: dict, found: dict[str, list[tuple[str, str]]], *, path: str
) -> None:
    node_type = node.get("type")
    field_type = _field_type(node)
    if field_type is not None:
        _record(node.get("id"), field_type, found, path)

    if node_type == "grid":
        items = node.get("items")
        if isinstance(items, list):
            for index, item in enumerate(items):
                if isinstance(item, dict):
                    _record(item.get("id"), "grid_row", found, f"{path}.items[{index}]")
        _collect_scope(node.get("row"), found, path=f"{path}.row")
        _collect_scope(node.get("header"), found, path=f"{path}.header")
        _collect_scope(node.get("content"), found, path=f"{path}.content")
        return

    if node_type == "repeater":
        _collect_scope(node.get("content"), found, path=f"{path}.content")
        _collect_scope(node.get("header"), found, path=f"{path}.header")
        return

    for key in _CHILD_ELEMENT_KEYS:
        _collect_scope(node.get(key), found, path=f"{path}.{key}")


def _record(
    node_id: object,
    field_type: str,
    found: dict[str, list[tuple[str, str]]],
    path: str,
) -> None:
    if isinstance(node_id, str) and node_id:
        found.setdefault(node_id, []).append((path, field_type))


@dataclass
class IdDiff:
    added: list[str]
    removed: list[str]


def validate_publish_ids(previous_layout: dict | None, new_layout: dict) -> IdDiff:
    """Enforce the publish-time id rules and return the added/removed ids.

    - No id may appear more than once in `new_layout`.
    - An id that also appeared in `previous_layout` must keep the same field
      type (renaming/moving a field is fine; turning it into a different kind
      of field is not -- give it a new id instead).
    - An id that's new relative to `previous_layout` must look server-minted
      (see `_ID_RE`) -- authors can't invent their own ids in the code editor;
      leave `id` blank and one is assigned automatically on save.
    """
    occurrences = collect_ids(new_layout)

    for node_id, entries in occurrences.items():
        if len(entries) > 1:
            paths = ", ".join(path for path, _ in entries)
            raise ValidationError(f"Field id '{node_id}' is used more than once ({paths})")

    new_types = {node_id: entries[0][1] for node_id, entries in occurrences.items()}
    previous_types = {
        node_id: entries[0][1] for node_id, entries in collect_ids(previous_layout).items()
    }

    for node_id, field_type in new_types.items():
        previous_type = previous_types.get(node_id)
        if previous_type is not None:
            if previous_type != field_type:
                raise ValidationError(
                    f"Field id '{node_id}' changed from a '{previous_type}' to a "
                    f"'{field_type}'; give it a new id instead of reusing this one"
                )
        elif not _ID_RE.match(node_id):
            raise ValidationError(
                f"Field id '{node_id}' wasn't assigned by the server; leave 'id' "
                "blank on new fields and one will be minted automatically"
            )

    added = sorted(set(new_types) - set(previous_types))
    removed = sorted(set(previous_types) - set(new_types))
    return IdDiff(added=added, removed=removed)
