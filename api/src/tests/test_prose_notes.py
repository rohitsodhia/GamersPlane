import copy

from app.helpers.prose import (
    all_note_recipient_ids,
    note_nodes,
    redact_notes,
)

SECRET = "the secret plan"


def para(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


def note(*user_ids, text=SECRET, mode=None):
    attrs = {"userIds": list(user_ids)}
    if mode is not None:
        attrs["mode"] = mode
    return {"type": "note", "attrs": attrs, "content": [para(text)]}


def dump(body):
    return repr(body)


class TestRedactNotes:
    def test_a_recipient_reads_the_note(self):
        body = doc(para("hi"), note(7))

        assert redact_notes(body, 7, False) == body

    def test_someone_else_gets_a_stub_without_the_text(self):
        body = doc(para("hi"), note(7, 8))

        redacted = redact_notes(body, 99, False)

        assert SECRET not in dump(redacted)
        assert redacted["content"][0] == para("hi")
        stub = redacted["content"][1]
        assert stub["type"] == "note"
        assert stub["attrs"] == {"mode": "note", "userIds": [7, 8], "hidden": True}
        # A note needs a block to parse, so the stub keeps one empty paragraph.
        assert stub["content"] == [{"type": "paragraph"}]

    def test_a_guest_gets_a_stub(self):
        redacted = redact_notes(doc(note(7)), None, False)

        assert SECRET not in dump(redacted)
        assert redacted["content"][0]["attrs"]["hidden"] is True

    def test_a_viewer_who_sees_all_notes_reads_every_one(self):
        body = doc(note(7), note(8, mode="private"), note())

        assert redact_notes(body, 99, True) == body

    def test_a_private_note_is_removed_for_everyone_else(self):
        body = doc(para("hi"), note(7, mode="private"))

        redacted = redact_notes(body, 99, False)

        assert redacted == doc(para("hi"))

    def test_a_private_note_is_still_read_by_its_recipient(self):
        body = doc(note(7, mode="private"))

        assert redact_notes(body, 7, False) == body

    def test_a_note_with_no_recipients_is_hidden_from_everyone_but_all_seers(self):
        private = doc(note(mode="private"))
        plain = doc(note())

        assert redact_notes(private, 7, False) == doc({"type": "paragraph"})
        stub = redact_notes(plain, 7, False)["content"][0]
        assert stub["attrs"] == {"mode": "note", "userIds": [], "hidden": True}
        assert redact_notes(plain, 7, True) == plain

    def test_notes_inside_a_quote_and_a_list_are_redacted(self):
        quote = {"type": "quote", "content": [para("said"), note(7)]}
        bullets = {
            "type": "bulletList",
            "content": [{"type": "listItem", "content": [note(7)]}],
        }

        redacted = redact_notes(doc(quote, bullets), 99, False)

        assert SECRET not in dump(redacted)
        assert len(note_nodes(redacted)) == 2

    def test_a_note_nested_in_a_readable_note_is_judged_on_its_own(self):
        inner = note(8, text="inner secret")
        outer = {"type": "note", "attrs": {"userIds": [7]}, "content": [inner]}

        redacted = redact_notes(doc(outer), 7, False)

        assert "inner secret" not in dump(redacted)
        outer_out = redacted["content"][0]
        assert outer_out["attrs"] == {"userIds": [7]}
        assert outer_out["content"][0]["attrs"]["hidden"] is True

    def test_a_note_nested_in_an_unreadable_note_goes_with_it(self):
        outer = {
            "type": "note",
            "attrs": {"userIds": [8]},
            "content": [note(7, text="inner secret")],
        }

        redacted = redact_notes(doc(outer), 7, False)

        assert "inner secret" not in dump(redacted)
        assert note_nodes(redacted)[0]["attrs"]["hidden"] is True
        assert len(note_nodes(redacted)) == 1

    def test_a_container_left_empty_by_a_removed_private_note_keeps_a_paragraph(self):
        quote = {"type": "quote", "content": [note(7, mode="private")]}

        redacted = redact_notes(doc(quote), 99, False)

        assert redacted["content"][0]["content"] == [{"type": "paragraph"}]

    def test_the_input_is_not_changed(self):
        body = doc(note(7), note(8, mode="private"))
        before = copy.deepcopy(body)

        redact_notes(body, 99, False)

        assert body == before

    def test_a_note_with_missing_or_malformed_attrs_is_a_stub_not_a_crash(self):
        bare = {"type": "note", "content": [para(SECRET)]}
        odd = {"type": "note", "attrs": {"userIds": "7", "mode": 3}, "content": []}

        redacted = redact_notes(doc(bare, odd), 7, False)

        assert SECRET not in dump(redacted)
        assert [n["attrs"]["userIds"] for n in note_nodes(redacted)] == [[], []]

    def test_a_document_that_is_itself_a_private_note_is_not_returned(self):
        redacted = redact_notes(note(7, mode="private"), 99, False)

        assert redacted == doc({"type": "paragraph"})


class TestAllNoteRecipientIds:
    def test_collects_distinct_valid_ids_from_every_note_in_order(self):
        quote = {"type": "quote", "content": [note(3, 4)]}
        body = doc(note(2, 3), quote, note("x", 0, True, 5))

        assert all_note_recipient_ids(body) == [2, 3, 4, 5]
