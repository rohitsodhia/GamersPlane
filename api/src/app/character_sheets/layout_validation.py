"""Structural validation for character-sheet layout documents.

The frontend renderer is lenient by design: an unknown element ``type`` or a
malformed formula renders nothing (with a dev-console warning) rather than
breaking the sheet. That is fine at render time, but it means a PATCH could
quietly persist a layout that is broken for everyone who opens the sheet later.

This module runs a shape check on the write path. It does not port every
renderer rule (per-type required keys, formula trees, the style allowlist) --
it only confirms the document matches the *general profile* of a sheet: the
top-level keys, and that every element node is an object carrying a known
``type`` with well-formed child arrays.

Anything that fails raises :class:`app.exceptions.ValidationError` with a
pointer to the offending node.
"""

from __future__ import annotations

from app.exceptions import ValidationError

SCHEMA_VERSION = 1

# Every element ``type`` the renderer knows (SHEET_AUTHORING.md sec. 11). Keep in
# sync with the frontend vocabulary; a type outside this set is almost always a
# typo, so we reject it rather than let the renderer silently drop the node.
KNOWN_ELEMENT_TYPES = frozenset(
    {
        "section",
        "group",
        "label",
        "header",
        "text",
        "input",
        "textarea",
        "select",
        "checkbox",
        "repeater",
        "grid",
        "grid_row",
        "grid_header",
        "list",
        "loop",
        "button",
        "collapsible",
        "collapsible-toggle",
    }
)

# Node keys that hold an ordered array of child element nodes. Other array-valued
# keys (``items`` on grid/loop, ``values`` on select, ``columns``, ``style_when``)
# are not element arrays and are left to the renderer.
_CHILD_ELEMENT_KEYS = ("content", "header", "row")

# Guards against a pathological deeply-nested payload blowing the recursion
# limit. Real sheets nest a handful of levels; 64 is far past anything sane.
_MAX_DEPTH = 64


def validate_sheet_layout(layout: object) -> None:
    """Raise ``ValidationError`` unless ``layout`` matches the sheet profile."""

    if not isinstance(layout, dict):
        raise ValidationError("Sheet layout must be a JSON object")

    if layout.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError(f"Sheet layout 'schema_version' must be {SCHEMA_VERSION}")

    if "classes" in layout and not isinstance(layout["classes"], dict):
        raise ValidationError("Sheet layout 'classes' must be a JSON object")

    elements = layout.get("elements")
    if not isinstance(elements, list):
        raise ValidationError("Sheet layout 'elements' must be an array")

    for index, node in enumerate(elements):
        _validate_node(node, path=f"elements[{index}]", depth=1)


def _validate_node(node: object, *, path: str, depth: int) -> None:
    if depth > _MAX_DEPTH:
        raise ValidationError(f"Sheet layout nests too deeply at {path}")

    if not isinstance(node, dict):
        raise ValidationError(f"Sheet element at {path} must be a JSON object")

    node_type = node.get("type")
    if not isinstance(node_type, str) or not node_type:
        raise ValidationError(f"Sheet element at {path} is missing a 'type'")

    if node_type not in KNOWN_ELEMENT_TYPES:
        raise ValidationError(f"Sheet element at {path} has unknown type '{node_type}'")

    for key in _CHILD_ELEMENT_KEYS:
        if key not in node:
            continue
        children = node[key]
        if not isinstance(children, list):
            raise ValidationError(f"Sheet element at {path}.{key} must be an array")
        for index, child in enumerate(children):
            _validate_node(child, path=f"{path}.{key}[{index}]", depth=depth + 1)


# Fields every published sheet must carry: name -> required element type.
REQUIRED_FIELDS = {"name": "input", "notes": "textarea"}

# Containers whose children write into the parent value scope, so a field
# inside one is still a single root-level value. ``loop`` is transparent too but
# can render its content many times, so a required field can't live in one.
_ROOT_SCOPE_CONTAINERS = frozenset({"section", "group", "list", "collapsible"})


def validate_publishable_layout(layout: object) -> None:
    """Shape check plus the fields every published sheet must have.

    Drafts only need :func:`validate_sheet_layout`; this is the stricter gate
    for publishing. Each required field must appear exactly once in the root
    value scope (repeater and grid content is per-row, so it doesn't count).
    """

    validate_sheet_layout(layout)

    found: dict[str, list[str]] = {name: [] for name in REQUIRED_FIELDS}
    _collect_root_fields(layout["elements"], found, path="elements")  # type: ignore[index]

    for name, element_type in REQUIRED_FIELDS.items():
        paths = found[name]
        if not paths:
            raise ValidationError(
                f"Sheet must have a top-level '{element_type}' named '{name}'"
            )
        if len(paths) > 1:
            raise ValidationError(
                f"Sheet has more than one '{name}' field ({', '.join(paths)})"
            )


def _collect_root_fields(
    nodes: list, found: dict[str, list[str]], *, path: str
) -> None:
    for index, node in enumerate(nodes):
        node_path = f"{path}[{index}]"
        node_type = node["type"]
        name = node.get("name")

        if name in REQUIRED_FIELDS:
            if node_type != REQUIRED_FIELDS[name]:
                raise ValidationError(
                    f"'{name}' at {node_path} must be a '{REQUIRED_FIELDS[name]}', "
                    f"not '{node_type}'"
                )
            found[name].append(node_path)

        if node_type in _ROOT_SCOPE_CONTAINERS:
            _collect_root_fields(
                node.get("content", []), found, path=f"{node_path}.content"
            )
