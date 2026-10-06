"""Publish-time check that every ref in a sheet layout resolves.

The frontend renderer resolves refs leniently: one that names nothing reads as
`0` (or, for `on_click.set`, makes the click a no-op), so a typo or a stale ref
after a rename silently breaks a formula instead of erroring. This module
rejects those at publish, using the same rules as the renderer -- keep it in
sync with `frontend/.../sheets/-components/refs.ts` and `createRefResolver` in
`loop-context.tsx` (scopes come from `layout_scopes.py`, the `scope-keys.ts`
mirror):

- A plain ref is an absolute dotted path from the sheet root:
  `hp`, or `stats.str.mod` (grid `stats`, row `str`, field `mod`). A single
  segment is always a root field, even inside a row.
- `$row.<path>` walks from the current repeater/grid row's scope.
- `$index` is the nearest `loop`'s iteration; `$item.<key>` reads a key of its
  current `items` entry.
- A path must end on a scalar field (an input/textarea/select/checkbox or a
  computed `text`). A whole grid, a grid row, or anything inside a repeater's
  rows is not a valid target.
- Any segment of a path may be a dynamic `$(inner)`, where `inner` is a ref
  whose value names that segment (`stats.$($row.stat).mod`). `inner` must be
  a select, an input/textarea, or `$item.<key>`. For a select or `$item`, the
  ref must resolve with every value it can take (blank options aside); free
  text can't be checked, so the path is only checked up to that segment.

Refs are checked in formulas (`text.formula`, `class_when`, `style_when[].when`,
a formula `loop.count`, `on_click.to`) and in `on_click.set`, which must name a
store field (`$index` / `$item` aren't writable).

Duplicate names in one scope aren't rejected here; like the renderer, the
first one wins.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product

from app.character_sheets.layout_scopes import Field, Scope, dicts, scope_for
from app.exceptions import ValidationError


@dataclass(frozen=True)
class _Loop:
    # The `items` entries; None for a `count` loop.
    items: tuple[dict, ...] | None


@dataclass(frozen=True)
class _Context:
    root: Scope
    # The enclosing repeater/grid row's scope, or None outside any row.
    row: Scope | None
    # The nearest enclosing loop, or None outside any loop.
    loop: _Loop | None


def validate_layout_refs(layout: dict) -> None:
    """Raise ``ValidationError`` on the first ref in `layout` that doesn't resolve.

    Expects a layout that already passed `validate_sheet_layout`.
    """
    elements = layout.get("elements")
    if not isinstance(elements, list):
        return
    context = _Context(root=scope_for(elements), row=None, loop=None)
    _check_nodes(elements, context, path="elements")


# --- walking the layout -------------------------------------------------------


def _check_nodes(nodes: object, context: _Context, *, path: str) -> None:
    if not isinstance(nodes, list):
        return
    for index, node in enumerate(nodes):
        if isinstance(node, dict):
            _check_node(node, context, path=f"{path}[{index}]")


def _check_node(node: dict, context: _Context, *, path: str) -> None:
    node_type = node.get("type")

    if node_type == "loop":
        # `count` is evaluated outside the loop; everything else (including
        # the loop's own `class_when` / `style_when`) once per iteration.
        count = node.get("count")
        if node.get("items") is None and isinstance(count, dict):
            _check_formula(count, context, path=f"{path}.count")
        inner = replace(context, loop=_loop_for(node))
        _check_styling(node, inner, path=path)
        _check_nodes(node.get("content"), inner, path=f"{path}.content")
        return

    _check_styling(node, context, path=path)

    if node_type == "text" and node.get("formula") is not None:
        _check_formula(node["formula"], context, path=f"{path}.formula")
    elif node_type == "button":
        _check_click(node.get("on_click"), context, path=f"{path}.on_click")

    if node_type == "repeater":
        _check_nodes(node.get("header"), context, path=f"{path}.header")
        row = replace(context, row=scope_for(node.get("content")))
        _check_nodes(node.get("content"), row, path=f"{path}.content")
    elif node_type == "grid":
        _check_grid(node, context, path=path)
    else:
        _check_nodes(node.get("content"), context, path=f"{path}.content")


def _check_grid(node: dict, context: _Context, *, path: str) -> None:
    # Only what the renderer draws: the compact form's `header` + `row`, or
    # the explicit form's `grid_header` / `grid_row` children (whose own
    # `class_when` / `style_when` the renderer ignores).
    if node.get("items") is not None:
        _check_nodes(node.get("header"), context, path=f"{path}.header")
        row = replace(context, row=scope_for(node.get("row")))
        _check_nodes(node.get("row"), row, path=f"{path}.row")
        return
    content = node.get("content")
    for index, child in enumerate(content if isinstance(content, list) else []):
        if not isinstance(child, dict):
            continue
        child_path = f"{path}.content[{index}].content"
        if child.get("type") == "grid_header":
            _check_nodes(child.get("content"), context, path=child_path)
        elif child.get("type") == "grid_row":
            row = replace(context, row=scope_for(child.get("content")))
            _check_nodes(child.get("content"), row, path=child_path)


def _loop_for(node: dict) -> _Loop:
    items = node.get("items")
    if not isinstance(items, list):
        return _Loop(items=None)
    return _Loop(items=tuple(dicts(items)))


def _check_styling(node: dict, context: _Context, *, path: str) -> None:
    class_when = node.get("class_when")
    if isinstance(class_when, dict):
        for class_name, expr in class_when.items():
            _check_formula(expr, context, path=f"{path}.class_when.{class_name}")
    style_when = node.get("style_when")
    if isinstance(style_when, list):
        for index, rule in enumerate(style_when):
            if isinstance(rule, dict):
                _check_formula(
                    rule.get("when"), context, path=f"{path}.style_when[{index}].when"
                )


def _check_click(action: object, context: _Context, *, path: str) -> None:
    if not isinstance(action, dict) or "set" not in action:
        return
    _check_ref(action["set"], context, path=f"{path}.set", target=True)
    _check_formula(action.get("to"), context, path=f"{path}.to")


def _check_formula(expr: object, context: _Context, *, path: str) -> None:
    if not isinstance(expr, dict):
        return
    if "ref" in expr:
        _check_ref(expr["ref"], context, path=path, target=False)
        return
    args = expr.get("args")
    if isinstance(args, list):
        for index, arg in enumerate(args):
            _check_formula(arg, context, path=f"{path}.args[{index}]")


# --- resolving one ref (mirrors `refs.ts` + `createRefResolver`) ---------------


class _Unresolved(Exception):
    """Why a ref doesn't resolve."""


@dataclass(frozen=True)
class _Dynamic:
    """A `$(inner)` segment: `inner` is resolved first and its value is used as
    the segment's name."""

    inner: str


type _Segment = str | _Dynamic

# A dynamic segment whose value can be any text (an `input`): the rest of the
# path can't be checked past it.
_ANY = None


def _check_ref(ref: object, context: _Context, *, path: str, target: bool) -> None:
    if not isinstance(ref, str):
        raise ValidationError(f"Ref at {path} must be a string")
    try:
        _resolve(ref, context, target=target)
    except _Unresolved as reason:
        raise ValidationError(
            f"Ref '{ref}' at {path} doesn't resolve: {reason}"
        ) from None


def _resolve(ref: str, context: _Context, *, target: bool) -> Field | None:
    """The field `ref` names in `context` -- None for a loop value, or when a
    dynamic segment hides it. Raises `_Unresolved` if it doesn't resolve.

    A dynamic segment is checked with every value it can take (a select's
    options, the loop items' values), so the ref must resolve for each."""
    if ref == "$index" or ref.startswith("$item."):
        _check_loop_ref(ref, context, target=target)
        return None

    segments = _split_ref(ref)
    head = segments[0]
    if head == "$row":
        if context.row is None:
            raise _Unresolved("'$row' is only available inside a repeater or grid row")
        if len(segments) == 1:
            raise _Unresolved("name a field after '$row' (e.g. '$row.score')")
        scope, segments, where = context.row, segments[1:], "in this row"
    elif isinstance(head, str) and head.startswith("$"):
        raise _Unresolved(f"'{head}' isn't a known '$' ref ($row, $item, $index)")
    else:
        scope, where = context.root, "at the sheet root"

    choices = [
        [segment] if isinstance(segment, str) else _names_for(segment, context)
        for segment in segments
    ]
    field = None
    for names in product(*choices):
        try:
            field = _walk(scope, list(names), where=where)
        except _Unresolved as reason:
            if (
                isinstance(head, str)
                and scope is context.root
                and context.row is not None
                and head in context.row
            ):
                reason = f"{reason} (to read this row's field, use '$row.{ref}')"
            raise _Unresolved(_when(segments, names) + str(reason)) from None
    return field


def _check_loop_ref(ref: str, context: _Context, *, target: bool) -> None:
    if target:
        raise _Unresolved("a button can only set a field, not a loop value")
    if context.loop is None:
        raise _Unresolved("it's only available inside a loop")
    if ref == "$index":
        return
    key = ref.removeprefix("$item.")
    if context.loop.items is None:
        raise _Unresolved("the enclosing loop uses 'count', so it has no items")
    if not any(key in item for item in context.loop.items):
        raise _Unresolved(f"no entry in the enclosing loop's items has a '{key}' key")


def _split_ref(ref: str) -> list[_Segment]:
    """`ref`'s dotted segments; a `$(...)` segment may itself contain dots."""
    segments: list[_Segment] = []
    i = 0
    while True:
        if ref.startswith("$(", i):
            close = ref.find(")", i)
            if close == -1:
                raise _Unresolved("a '$(' is never closed")
            inner = ref[i + 2 : close]
            if not inner:
                raise _Unresolved("'$()' is empty; put a ref inside it")
            if "$(" in inner:
                raise _Unresolved("'$(...)' can't be nested")
            segments.append(_Dynamic(inner))
            i = close + 1
            if i == len(ref):
                return segments
            if ref[i] != ".":
                raise _Unresolved("'$(...)' must be a whole segment")
        else:
            dot = ref.find(".", i)
            name = ref[i:] if dot == -1 else ref[i:dot]
            if not name:
                raise _Unresolved("it has an empty segment")
            if "$(" in name:
                raise _Unresolved("'$(...)' must be a whole segment")
            segments.append(name)
            if dot == -1:
                return segments
            i = dot
        i += 1


def _names_for(segment: _Dynamic, context: _Context) -> list[str | None]:
    """Every name `segment` can stand for, or `[_ANY]` when its value is free
    text. Raises `_Unresolved` if it can't hold a name at all."""
    inner = segment.inner
    try:
        field = _resolve(inner, context, target=False)
    except _Unresolved as reason:
        raise _Unresolved(f"in '$({inner})': {reason}") from None

    if inner == "$index":
        raise _Unresolved("'$index' is a number, so it can't be used in '$(...)'")
    if inner.startswith("$item."):
        key = inner.removeprefix("$item.")
        items = context.loop.items if context.loop else ()
        names = [item.get(key) for item in items or ()]
        names = list(dict.fromkeys(n for n in names if isinstance(n, str) and n))
        if not names:
            raise _Unresolved(f"no '{key}' in the enclosing loop's items is a name")
        return names

    assert field is not None
    if field.element_type in ("input", "textarea"):
        return [_ANY]
    if field.element_type == "select":
        if not field.options:
            raise _Unresolved(f"'{inner}' has no options to use in '$(...)'")
        return list(field.options)
    what = "checkbox" if field.element_type == "checkbox" else "computed value"
    raise _Unresolved(f"'{inner}' is a {what}, so it can't be used in '$(...)'")


def _when(segments: list[_Segment], names: tuple[str | None, ...]) -> str:
    """A "when '<inner>' is '<name>': " prefix giving each dynamic segment's
    value in `names`, so an error says which option broke the ref."""
    picked = [
        f"'{segment.inner}' is '{name}'"
        for segment, name in zip(segments, names, strict=True)
        if isinstance(segment, _Dynamic) and name is not _ANY
    ]
    return f"when {' and '.join(picked)}: " if picked else ""


def _walk(scope: Scope, names: list[str | None], *, where: str) -> Field | None:
    """The scalar field `names` leads to from `scope`; None once it reaches an
    `_ANY` segment. Raises `_Unresolved` if it doesn't lead to one."""
    head, rest = names[0], names[1:]
    if head is _ANY:
        return None
    field = scope.get(head)
    if field is None:
        raise _Unresolved(f"there's no field named '{head}' {where}")

    if field.kind == "value":
        if rest:
            raise _Unresolved(f"'{head}' is a single field, not a grid")
        return field
    if field.kind == "repeater":
        raise _Unresolved(f"'{head}' is a repeater; refs can't read into its rows")

    if not rest:
        raise _Unresolved(
            f"'{head}' is a grid; name a row and a field ('{head}.<row>.<field>')"
        )
    row_key, in_row = rest[0], rest[1:]
    if row_key is _ANY:
        return None
    row = (field.rows or {}).get(row_key)
    if row is None:
        raise _Unresolved(f"grid '{head}' has no row '{row_key}'")
    if not in_row:
        raise _Unresolved(f"'{head}.{row_key}' is a grid row; name a field in it")
    return _walk(row.scope, in_row, where=f"in row '{row_key}' of grid '{head}'")
