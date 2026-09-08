import json
from pathlib import Path

_DEFAULT_LAYOUT_TEXT = (Path(__file__).parent / "default_layout.json").read_text(
    encoding="utf-8"
)


def empty_sheet_layout() -> dict:
    """The minimal valid layout: the keys the renderer expects, no elements.

    Used as the fallback when a sheet is created without an explicit layout, so
    a row never holds a shape the frontend can't render.
    """
    return {"schema_version": 1, "classes": {}, "elements": []}


def default_sheet_layout() -> dict:
    """Starter layout seeded into every newly created character sheet.

    The shape lives in ``default_layout.json`` alongside this module so the
    default can be changed without a code edit or migration. Parsed fresh on
    each call so the caller gets an isolated dict it may mutate.
    """
    return json.loads(_DEFAULT_LAYOUT_TEXT)
