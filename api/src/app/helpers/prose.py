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


IMAGE_NODE_TYPES = frozenset({"image", "imageUpload"})
MENTION_NODE_TYPE = "mention"
# What an @mention reads as when its user is gone or unknown.
DELETED_MENTION_NAME = "[deleted]"


def _collect(
    node: dict,
    parts: list[str],
    npc_names: dict[int, str],
    image_placeholder: str | None = None,
    user_names: dict[int, str] | None = None,
) -> None:
    node_type = node.get("type")
    if node_type in EXCLUDED_NODE_TYPES:
        # Still a block boundary, so the text around it doesn't run together.
        parts.append(" ")
        return
    if node_type == "text":
        parts.append(node.get("text", ""))
        return
    if node_type == MENTION_NODE_TYPE:
        # Inline, so no trailing separator: "@bob, hi" must not become "@bob , hi".
        user_id = (node.get("attrs") or {}).get("userId")
        name = (user_names or {}).get(user_id) if isinstance(user_id, int) else None
        parts.append(f"@{name or DELETED_MENTION_NAME}")
        return
    if node_type in IMAGE_NODE_TYPES and image_placeholder is not None:
        parts.append(f" {image_placeholder} ")
        return
    if node_type == SPEAKER_NODE_TYPE:
        npc_id = (node.get("attrs") or {}).get("npcId")
        name = npc_names.get(npc_id) if isinstance(npc_id, int) else None
        if name:
            parts.append(f" {name}: ")
    if node_type == ROSTER_NODE_TYPE:
        parts.append(f" {_roster_text(node.get('attrs') or {}, npc_names)} ")
    for child in node.get("content") or []:
        _collect(child, parts, npc_names, image_placeholder, user_names)
    # Block nodes, hard breaks and rules all separate the text around them.
    parts.append(" ")


def prose_to_text(
    body: dict,
    npc_names: dict[int, str] | None = None,
    image_placeholder: str | None = None,
    user_names: dict[int, str] | None = None,
) -> str:
    """The visible text of a document, with whitespace collapsed to single spaces.

    A quick NPC speaker block's text is kept, prefixed with ``"Name: "`` when its
    id is in ``npc_names`` (this function has no database access). A roster block
    becomes ``"Title: Name, Name"`` from the same names. Images contribute nothing
    unless ``image_placeholder`` is given, which then stands in for each one. An
    @mention becomes ``"@username"`` from ``user_names``, or ``"@[deleted]"`` when
    its id isn't in there.
    """
    parts: list[str] = []
    _collect(body, parts, npc_names or {}, image_placeholder, user_names)
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


def _walk_visible(node: object):
    """Like ``_walk``, but without descending into quotes and notes (and not
    yielding them either)."""
    if not isinstance(node, dict) or node.get("type") in EXCLUDED_NODE_TYPES:
        return
    yield node
    content = node.get("content")
    for child in content if isinstance(content, list) else []:
        yield from _walk_visible(child)


def _mention_user_id(node: dict) -> object:
    attrs = node.get("attrs")
    return attrs.get("userId") if isinstance(attrs, dict) else None


def raw_mention_user_ids(body: dict) -> list:
    """The ``userId`` of every mention node in the document, quoted ones too, as
    stored (so possibly missing or not an int), in document order."""
    return [
        _mention_user_id(node)
        for node in _walk(body)
        if node.get("type") == MENTION_NODE_TYPE
    ]


def all_mention_user_ids(body: dict) -> list[int]:
    """The distinct, well-formed user ids of every mention node in the document,
    quoted ones too (they still render), in order of first appearance."""
    ids = [i for i in raw_mention_user_ids(body) if is_valid_id(i)]
    return list(dict.fromkeys(ids))


def mentioned_user_ids(body: dict) -> list[int]:
    """The distinct, well-formed ids of the users the document actually mentions,
    in order of first appearance. Mentions inside a quote (someone else's words),
    blockquote or note don't count."""
    ids = [
        user_id
        for node in _walk_visible(body)
        if node.get("type") == MENTION_NODE_TYPE
        and is_valid_id(user_id := _mention_user_id(node))
    ]
    return list(dict.fromkeys(ids))


def prose_snippet(
    body: dict,
    limit: int,
    npc_names: dict[int, str] | None = None,
    image_placeholder: str | None = None,
    user_names: dict[int, str] | None = None,
) -> str:
    """``prose_to_text`` cut to at most ``limit`` characters, ending in an ellipsis
    when it was cut."""
    text = prose_to_text(body, npc_names, image_placeholder, user_names)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
