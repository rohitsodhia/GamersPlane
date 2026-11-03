def prose_doc(text: str) -> dict:
    """Minimal ProseMirror/TipTap document JSON wrapping a single text paragraph."""
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def mentioning_doc(*user_ids: int) -> dict:
    """A document with one paragraph holding an @mention of each given user."""
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "mention", "attrs": {"userId": user_id}}
                    for user_id in user_ids
                ],
            }
        ],
    }
