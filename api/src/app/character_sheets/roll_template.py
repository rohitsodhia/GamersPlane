"""`${ref}` templates for a sheet element's `roll` (``dice`` and ``reason``).

A template is literal text with ``${...}`` placeholders; a placeholder holds a
ref path only (``str_mod``, ``$row.bonus``, ``stats.$(pick).mod``), never a
formula. This module is the one place the API parses them, for both the shape
check in ``layout_validation`` and the ref check in ``layout_refs``. The
frontend mirrors the parser, the sign tidy-up and the single-d20 test in
``roll.ts`` -- keep them in sync.
"""

from __future__ import annotations

import re
from typing import Literal

type TemplatePart = tuple[Literal["text", "ref"], str]


class TemplateSyntaxError(ValueError):
    """An unterminated or empty ``${}`` in a template."""


def parse_template(template: str) -> list[TemplatePart]:
    """Split ``template`` into ``("text", ...)`` and ``("ref", ...)`` parts.

    A ref runs to the ``}`` that closes its ``${``, skipping any ``(...)`` or
    ``{...}`` nested inside it (a dynamic ``$(...)`` segment).
    """
    parts: list[TemplatePart] = []
    pos = 0
    while pos < len(template):
        opening = template.find("${", pos)
        if opening == -1:
            break
        if opening > pos:
            parts.append(("text", template[pos:opening]))
        depth = 0
        end = -1
        for i in range(opening + 2, len(template)):
            char = template[i]
            if char in "({":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "}":
                if depth == 0:
                    end = i
                    break
                depth -= 1
        if end == -1:
            raise TemplateSyntaxError("has an unterminated '${'")
        ref = template[opening + 2 : end].strip()
        if not ref:
            raise TemplateSyntaxError("has an empty '${}'")
        parts.append(("ref", ref))
        pos = end + 1
    if pos < len(template):
        parts.append(("text", template[pos:]))
    return parts


def template_refs(template: str) -> list[str]:
    """The ref paths in ``template`` (raises ``TemplateSyntaxError``)."""
    return [value for kind, value in parse_template(template) if kind == "ref"]


def normalize_dice(dice: str) -> str:
    """Tidy a substituted dice string: strip spaces, collapse runs of signs
    (``+-``/``-+`` to ``-``, ``--``/``++`` to ``+``), drop a bare ``+0``/``-0``
    modifier term (never ``+0d6`` or the 0 in ``10``), drop a ``+`` that leads a
    group."""
    dice = dice.replace(" ", "")
    dice = re.sub(r"[+-]{2,}", lambda m: "-" if m.group().count("-") % 2 else "+", dice)
    dice = re.sub(r"[+-]0(?![0-9d])", "", dice, flags=re.IGNORECASE)
    return re.sub(r"(^|,)\+", r"\1", dice)


# A single-die d20 term: `d20` or `1d20`, on its own (not 11d20, not d20h1).
_SINGLE_D20_RE = re.compile(r"(?<![^+,\-])1?d20(?![0-9hl])", re.IGNORECASE)


def has_single_d20(dice: str) -> bool:
    return _SINGLE_D20_RE.search(dice) is not None
