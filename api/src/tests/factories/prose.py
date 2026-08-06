def prose_doc(text: str) -> dict:
    """Minimal ProseMirror/TipTap document JSON wrapping a single text paragraph."""
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }
