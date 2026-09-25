import re

import pytest

from app.character_sheets.defaults import default_sheet_layout
from app.character_sheets.layout_ids import (
    collect_ids,
    mint_ids,
    validate_publish_ids,
)
from app.exceptions import ValidationError

_ID_RE = re.compile(r"^[0-9a-f]{8}$")


def _layout(*elements, classes=None):
    return {"schema_version": 1, "classes": classes or {}, "elements": list(elements)}


class TestMintIds:
    def test_mints_ids_on_the_default_layout(self):
        layout = mint_ids(default_sheet_layout())

        name_input = layout["elements"][0]["content"][0]["content"][1]
        notes_textarea = layout["elements"][1]["content"][1]
        assert _ID_RE.match(name_input["id"])
        assert _ID_RE.match(notes_textarea["id"])
        assert name_input["id"] != notes_textarea["id"]

    def test_leaves_decorative_nodes_without_an_id(self):
        layout = mint_ids(
            _layout(
                {"type": "section", "content": [{"type": "label", "text": "Name"}]}
            )
        )

        section = layout["elements"][0]
        label = section["content"][0]
        assert "id" not in section
        assert "id" not in label

    def test_mints_ids_for_every_value_bearing_type(self):
        layout = mint_ids(
            _layout(
                {"type": "input", "name": "a"},
                {"type": "textarea", "name": "b"},
                {"type": "select", "name": "c", "values": ["x"]},
                {"type": "checkbox", "name": "d"},
                {"type": "text", "name": "e", "formula": {"lit": 1}},
                {"type": "repeater", "name": "f", "content": []},
                {"type": "grid", "name": "g", "content": []},
            )
        )

        ids = [node["id"] for node in layout["elements"]]
        assert all(_ID_RE.match(node_id) for node_id in ids)
        assert len(set(ids)) == len(ids)

    def test_does_not_mint_an_id_for_a_literal_text_node(self):
        layout = mint_ids(_layout({"type": "text", "text": "hi"}))

        assert "id" not in layout["elements"][0]

    def test_leaves_an_existing_id_alone(self):
        layout = mint_ids(_layout({"type": "input", "name": "a", "id": "deadbeef"}))

        assert layout["elements"][0]["id"] == "deadbeef"

    def test_regenerates_a_duplicate_id_in_the_same_scope(self):
        layout = mint_ids(
            _layout(
                {"type": "input", "name": "a", "id": "deadbeef"},
                {"type": "input", "name": "b", "id": "deadbeef"},
            )
        )

        first, second = (node["id"] for node in layout["elements"])
        assert first == "deadbeef"
        assert second != "deadbeef"
        assert _ID_RE.match(second)

    def test_mints_ids_for_repeater_row_template_fields(self):
        layout = mint_ids(
            _layout(
                {
                    "type": "repeater",
                    "name": "skills",
                    "content": [{"type": "input", "name": "skill"}],
                    "header": [{"type": "input", "name": "unused_but_fine"}],
                }
            )
        )

        repeater = layout["elements"][0]
        assert _ID_RE.match(repeater["id"])
        assert _ID_RE.match(repeater["content"][0]["id"])
        assert _ID_RE.match(repeater["header"][0]["id"])

    def test_repeater_row_template_ids_may_reuse_a_root_id(self):
        # Different scopes, so the 8-char space doesn't need to avoid a root id.
        layout = mint_ids(
            _layout(
                {"type": "input", "name": "a", "id": "deadbeef"},
                {
                    "type": "repeater",
                    "name": "rows",
                    "content": [{"type": "input", "name": "b", "id": "deadbeef"}],
                },
            )
        )

        assert layout["elements"][0]["id"] == "deadbeef"
        assert layout["elements"][1]["content"][0]["id"] == "deadbeef"

    def test_mints_ids_for_compact_grid_items_and_row_template(self):
        layout = mint_ids(
            _layout(
                {
                    "type": "grid",
                    "name": "stats",
                    "items": [{"key": "str", "label": "STR"}, {"key": "dex", "label": "DEX"}],
                    "row": [{"type": "input", "name": "score"}],
                }
            )
        )

        grid = layout["elements"][0]
        item_ids = [item["id"] for item in grid["items"]]
        assert all(_ID_RE.match(i) for i in item_ids)
        assert len(set(item_ids)) == 2
        assert _ID_RE.match(grid["row"][0]["id"])

    def test_mints_ids_for_explicit_grid_rows_and_header_in_the_root_scope(self):
        layout = mint_ids(
            _layout(
                {
                    "type": "grid",
                    "name": "stats",
                    "content": [
                        {
                            "type": "grid_header",
                            "content": [{"type": "text", "text": "Score"}],
                        },
                        {
                            "type": "grid_row",
                            "key": "str",
                            "content": [{"type": "input", "name": "score"}],
                        },
                    ],
                },
            )
        )

        grid_row = layout["elements"][0]["content"][1]
        assert _ID_RE.match(grid_row["id"])

    def test_is_idempotent(self):
        layout = mint_ids(default_sheet_layout())
        ids_before = _first_types(collect_ids(layout))

        mint_ids(layout)
        ids_after = _first_types(collect_ids(layout))

        assert ids_before == ids_after


def _first_types(occurrences):
    return {node_id: entries[0][1] for node_id, entries in occurrences.items()}


class TestCollectIds:
    def test_collects_nothing_from_an_empty_layout(self):
        assert collect_ids(_layout()) == {}

    def test_collects_grid_items_as_grid_row_type(self):
        layout = _layout(
            {
                "type": "grid",
                "name": "stats",
                "items": [{"id": "aaaaaaaa", "key": "str", "label": "STR"}],
                "row": [],
            }
        )

        found = collect_ids(layout)
        assert found["aaaaaaaa"] == [("elements[0].items[0]", "grid_row")]

    def test_none_layout_collects_nothing(self):
        assert collect_ids(None) == {}


class TestValidatePublishIds:
    def test_accepts_a_layout_with_no_previous_version(self):
        layout = mint_ids(_layout({"type": "input", "name": "a"}))

        diff = validate_publish_ids(None, layout)

        assert diff.added == [layout["elements"][0]["id"]]
        assert diff.removed == []

    def test_accepts_a_kept_id_of_the_same_type(self):
        previous = mint_ids(_layout({"type": "input", "name": "a"}))
        node_id = previous["elements"][0]["id"]
        new = _layout({"type": "input", "name": "renamed", "id": node_id})

        diff = validate_publish_ids(previous, new)

        assert diff.added == []
        assert diff.removed == []

    def test_rejects_a_kept_id_that_changed_type(self):
        previous = mint_ids(_layout({"type": "input", "name": "a"}))
        node_id = previous["elements"][0]["id"]
        new = _layout({"type": "select", "name": "a", "id": node_id, "values": ["x"]})

        with pytest.raises(ValidationError, match="changed from a 'input' to a 'select'"):
            validate_publish_ids(previous, new)

    def test_rejects_a_hand_authored_id_on_a_new_field(self):
        new = _layout({"type": "input", "name": "a", "id": "not-server-minted"})

        with pytest.raises(ValidationError, match="wasn't assigned by the server"):
            validate_publish_ids(None, new)

    def test_rejects_a_duplicate_id(self):
        new = _layout(
            {"type": "input", "name": "a", "id": "aaaaaaaa"},
            {"type": "input", "name": "b", "id": "aaaaaaaa"},
        )

        with pytest.raises(ValidationError, match="used more than once"):
            validate_publish_ids(None, new)

    def test_reports_added_and_removed_ids(self):
        previous = mint_ids(
            _layout({"type": "input", "name": "a"}, {"type": "input", "name": "b"})
        )
        kept_id = previous["elements"][0]["id"]
        new = mint_ids(
            _layout(
                {"type": "input", "name": "a", "id": kept_id},
                {"type": "input", "name": "c"},
            )
        )

        diff = validate_publish_ids(previous, new)

        removed_id = previous["elements"][1]["id"]
        added_id = new["elements"][1]["id"]
        assert diff.added == [added_id]
        assert diff.removed == [removed_id]
