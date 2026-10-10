"""Plain-text extraction from ProseMirror/TipTap document JSON."""

# Nodes whose content must not leak into a text excerpt: quotes repeat someone
# else's post, and a note is hidden from everyone but the users it names.
EXCLUDED_NODE_TYPES = frozenset({"quote", "blockquote", "note"})


def _collect(node: dict, parts: list[str]) -> None:
    node_type = node.get("type")
    if node_type in EXCLUDED_NODE_TYPES:
        # Still a block boundary, so the text around it doesn't run together.
        parts.append(" ")
        return
    if node_type == "text":
        parts.append(node.get("text", ""))
        return
    for child in node.get("content") or []:
        _collect(child, parts)
    # Block nodes, hard breaks and rules all separate the text around them.
    parts.append(" ")


def prose_to_text(body: dict) -> str:
    """The visible text of a document, with whitespace collapsed to single spaces."""
    parts: list[str] = []
    _collect(body, parts)
    return " ".join("".join(parts).split())


def prose_snippet(body: dict, limit: int) -> str:
    """``prose_to_text`` cut to at most ``limit`` characters, ending in an ellipsis
    when it was cut."""
    text = prose_to_text(body)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
