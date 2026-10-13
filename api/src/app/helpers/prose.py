"""Plain-text extraction from ProseMirror/TipTap document JSON."""

# Nodes whose content must not leak into a text excerpt: quotes repeat someone
# else's post, and a note is hidden from everyone but the users it names.
EXCLUDED_NODE_TYPES = frozenset({"quote", "blockquote", "note"})


SPEAKER_NODE_TYPE = "npcSpeaker"
ROSTER_NODE_TYPE = "npcRoster"
MAX_ROSTER_TITLE_LENGTH = 100


def _roster_text(attrs: dict, npc_names: dict[int, str]) -> str:
    """``"Title: Name, Name"`` for a roster block's attrs (just the names when it
    has no title; unknown NPCs are left out)."""
    raw_ids = attrs.get("npcIds")
    names = [
        npc_names[npc_id]
        for npc_id in (raw_ids if isinstance(raw_ids, list) else [])
        if isinstance(npc_id, int) and npc_id in npc_names
    ]
    title = attrs.get("title")
    title = title.strip() if isinstance(title, str) else ""
    listed = ", ".join(names)
    if title and listed:
        return f"{title}: {listed}"
    return title or listed


def _collect(node: dict, parts: list[str], npc_names: dict[int, str]) -> None:
    node_type = node.get("type")
    if node_type in EXCLUDED_NODE_TYPES:
        # Still a block boundary, so the text around it doesn't run together.
        parts.append(" ")
        return
    if node_type == "text":
        parts.append(node.get("text", ""))
        return
    if node_type == SPEAKER_NODE_TYPE:
        npc_id = (node.get("attrs") or {}).get("npcId")
        name = npc_names.get(npc_id) if isinstance(npc_id, int) else None
        if name:
            parts.append(f" {name}: ")
    if node_type == ROSTER_NODE_TYPE:
        parts.append(f" {_roster_text(node.get('attrs') or {}, npc_names)} ")
    for child in node.get("content") or []:
        _collect(child, parts, npc_names)
    # Block nodes, hard breaks and rules all separate the text around them.
    parts.append(" ")


def prose_to_text(body: dict, npc_names: dict[int, str] | None = None) -> str:
    """The visible text of a document, with whitespace collapsed to single spaces.

    A quick NPC speaker block's text is kept, prefixed with ``"Name: "`` when its
    id is in ``npc_names`` (this function has no database access). A roster block
    becomes ``"Title: Name, Name"`` from the same names.
    """
    parts: list[str] = []
    _collect(body, parts, npc_names or {})
    return " ".join("".join(parts).split())


def _walk(node: object):
    """Every dict node in the document, parents before children."""
    if not isinstance(node, dict):
        return
    yield node
    content = node.get("content")
    for child in content if isinstance(content, list) else []:
        yield from _walk(child)


def roster_attrs(body: dict) -> list[dict]:
    """The attrs of every roster block in the document, in document order."""
    found = []
    for node in _walk(body):
        if node.get("type") == ROSTER_NODE_TYPE:
            attrs = node.get("attrs")
            found.append(attrs if isinstance(attrs, dict) else {})
    return found


def raw_content_npc_ids(body: dict) -> list:
    """The NPC ids named by the document's speaker blocks (``npcId``) and roster
    blocks (each of ``npcIds``), as stored (so possibly missing or not an int), in
    document order. A roster whose ``npcIds`` isn't a list contributes ``None``."""
    found: list = []
    for node in _walk(body):
        node_type = node.get("type")
        attrs = node.get("attrs")
        attrs = attrs if isinstance(attrs, dict) else {}
        if node_type == SPEAKER_NODE_TYPE:
            found.append(attrs.get("npcId"))
        elif node_type == ROSTER_NODE_TYPE:
            ids = attrs.get("npcIds")
            found.extend(ids if isinstance(ids, list) else [None])
    return found


MAX_ID = 2**31 - 1


def is_valid_id(value: object) -> bool:
    """Whether ``value`` could be a database id (a positive 32-bit int)."""
    return (
        isinstance(value, int) and not isinstance(value, bool) and 0 < value <= MAX_ID
    )


def content_npc_ids(body: dict) -> list[int]:
    """The distinct, well-formed quick NPC ids named by speaker and roster blocks
    anywhere in the document, in order of first appearance."""
    ids = [npc_id for npc_id in raw_content_npc_ids(body) if is_valid_id(npc_id)]
    return list(dict.fromkeys(ids))


def prose_snippet(
    body: dict, limit: int, npc_names: dict[int, str] | None = None
) -> str:
    """``prose_to_text`` cut to at most ``limit`` characters, ending in an ellipsis
    when it was cut."""
    text = prose_to_text(body, npc_names)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
