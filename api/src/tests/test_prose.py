from app.helpers.prose import prose_snippet, prose_to_text
from tests.factories import prose_doc


def para(*texts):
    return {
        "type": "paragraph",
        "content": [{"type": "text", "text": text} for text in texts],
    }


def doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


class TestProseToText:
    def test_adjacent_text_nodes_in_a_paragraph_are_joined_without_a_gap(self):
        assert prose_to_text(doc(para("Hel", "lo ", "world"))) == "Hello world"

    def test_blocks_are_separated_by_a_space(self):
        assert prose_to_text(doc(para("One"), para("Two"))) == "One Two"

    def test_nested_blocks_are_walked(self):
        bullets = {
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [para("a")]},
                {"type": "listItem", "content": [para("b")]},
            ],
        }

        assert prose_to_text(doc(bullets)) == "a b"

    def test_hard_break_separates_words(self):
        paragraph = {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "line one"},
                {"type": "hardBreak"},
                {"type": "text", "text": "line two"},
            ],
        }

        assert prose_to_text(doc(paragraph)) == "line one line two"

    def test_whitespace_is_collapsed(self):
        assert prose_to_text(doc(para("  a \n\n b  "), para(""))) == "a b"

    def test_quote_note_and_blockquote_are_skipped(self):
        body = doc(
            para("before"),
            {"type": "quote", "attrs": {"quotee": "bob"}, "content": [para("quoted")]},
            {"type": "note", "attrs": {"users": ["al"]}, "content": [para("secret")]},
            {"type": "blockquote", "content": [para("also quoted")]},
            para("after"),
        )

        assert prose_to_text(body) == "before after"

    def test_quote_nested_inside_another_block_is_skipped(self):
        item = {
            "type": "listItem",
            "content": [
                para("keep"),
                {"type": "quote", "content": [para("drop")]},
            ],
        }

        assert prose_to_text(doc({"type": "bulletList", "content": [item]})) == "keep"

    def test_empty_doc_is_empty(self):
        assert prose_to_text({"type": "doc", "content": []}) == ""


class TestProseSnippet:
    def test_short_text_is_returned_whole(self):
        assert prose_snippet(prose_doc("short"), 200) == "short"

    def test_text_at_the_limit_is_not_cut(self):
        assert prose_snippet(prose_doc("a" * 200), 200) == "a" * 200

    def test_longer_text_is_cut_to_the_limit_with_an_ellipsis(self):
        snippet = prose_snippet(prose_doc("a" * 300), 200)

        assert snippet == "a" * 199 + "…"
        assert len(snippet) == 200
