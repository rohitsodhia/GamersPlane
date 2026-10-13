from app.helpers.prose import (
    prose_snippet,
    prose_to_text,
    raw_content_npc_ids,
    content_npc_ids,
)
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


def speaker(npc_id, *blocks):
    return {"type": "npcSpeaker", "attrs": {"npcId": npc_id}, "content": list(blocks)}


class TestSpeakerBlocks:
    def test_text_is_kept_and_prefixed_with_the_name_when_known(self):
        body = doc(para("Intro"), speaker(4, para("Halt!")), para("Outro"))

        assert prose_to_text(body, {4: "Guard"}) == "Intro Guard: Halt! Outro"

    def test_text_is_kept_without_a_prefix_when_the_name_is_unknown(self):
        body = doc(speaker(4, para("Halt!")))

        assert prose_to_text(body) == "Halt!"
        assert prose_to_text(body, {9: "Other"}) == "Halt!"

    def test_each_block_gets_its_own_speaker(self):
        body = doc(speaker(1, para("Hi")), speaker(2, para("Bye")))

        assert prose_to_text(body, {1: "Al", 2: "Bo"}) == "Al: Hi Bo: Bye"

    def test_snippet_passes_names_through(self):
        body = doc(speaker(1, para("Hi")))

        assert prose_snippet(body, 200, {1: "Al"}) == "Al: Hi"


def roster(npc_ids, title=""):
    return {"type": "npcRoster", "attrs": {"title": title, "npcIds": npc_ids}}


class TestRosterBlocks:
    def test_text_is_the_title_and_the_names(self):
        body = doc(para("Intro"), roster([1, 2], "The Guard"), para("Outro"))

        assert (
            prose_to_text(body, {1: "Al", 2: "Bo"}) == "Intro The Guard: Al, Bo Outro"
        )

    def test_without_a_title_it_is_just_the_names(self):
        assert prose_to_text(doc(roster([1, 2])), {1: "Al", 2: "Bo"}) == "Al, Bo"

    def test_unknown_names_are_left_out(self):
        body = doc(roster([1, 9, 2], "Crew"))

        assert prose_to_text(body, {1: "Al", 2: "Bo"}) == "Crew: Al, Bo"

    def test_no_known_names_leaves_only_the_title(self):
        assert prose_to_text(doc(roster([9], "Crew"))) == "Crew"

    def test_no_title_and_no_known_names_leaves_nothing(self):
        assert prose_to_text(doc(para("a"), roster([9]), para("b"))) == "a b"

    def test_ids_are_collected_with_speakers_in_order(self):
        nested = {
            "type": "bulletList",
            "content": [{"type": "listItem", "content": [roster([5, 3])]}],
        }
        body = doc(speaker(3, para("a")), nested, roster([8, 5]))

        assert content_npc_ids(body) == [3, 5, 8]

    def test_malformed_ids_show_in_the_raw_list(self):
        body = doc(roster(["1", True, 4]), {"type": "npcRoster", "attrs": {}})

        assert content_npc_ids(body) == [4]
        assert raw_content_npc_ids(body) == ["1", True, 4, None]


class TestContentNpcIds:
    def test_ids_are_collected_recursively_in_order_without_repeats(self):
        nested = {
            "type": "bulletList",
            "content": [{"type": "listItem", "content": [speaker(7, para("x"))]}],
        }
        body = doc(speaker(3, para("a")), nested, speaker(3, para("b")), speaker(5))

        assert content_npc_ids(body) == [3, 7, 5]

    def test_malformed_ids_are_skipped_but_visible_in_the_raw_list(self):
        body = doc(
            speaker("3"), speaker(None), speaker(True), speaker(2**40), speaker(6)
        )

        assert content_npc_ids(body) == [6]
        assert raw_content_npc_ids(body) == ["3", None, True, 2**40, 6]

    def test_a_speaker_with_no_attrs_is_malformed(self):
        body = doc({"type": "npcSpeaker", "content": []})

        assert raw_content_npc_ids(body) == [None]


class TestProseSnippet:
    def test_short_text_is_returned_whole(self):
        assert prose_snippet(prose_doc("short"), 200) == "short"

    def test_text_at_the_limit_is_not_cut(self):
        assert prose_snippet(prose_doc("a" * 200), 200) == "a" * 200

    def test_longer_text_is_cut_to_the_limit_with_an_ellipsis(self):
        snippet = prose_snippet(prose_doc("a" * 300), 200)

        assert snippet == "a" * 199 + "…"
        assert len(snippet) == 200
