import re

import pytest

from app.character_sheets.character_values import (
    hidden_values,
    validate_character_values,
)
from app.exceptions import ValidationError

LAYOUT = {
    "schema_version": 1,
    "elements": [
        {"type": "input", "name": "hp", "id": "hp1"},
        {"type": "text", "name": "total", "id": "tot1", "formula": {"ref": "hp"}},
        {
            "type": "repeater",
            "name": "classes",
            "id": "cls1",
            "header": [{"type": "input", "name": "notes", "id": "not1"}],
            "content": [{"type": "input", "name": "level", "id": "lvl1"}],
        },
        {
            "type": "grid",
            "name": "stats",
            "id": "sts1",
            "items": [
                {"key": "str", "label": "STR", "id": "str1"},
                {"key": "dex", "label": "DEX", "id": "dex1"},
            ],
            "row": [{"type": "input", "name": "score", "id": "scr1"}],
        },
        {
            "type": "grid",
            "name": "saves",
            "id": "svs1",
            "content": [
                {
                    "type": "grid_row",
                    "key": "fort",
                    "id": "frt1",
                    "content": [{"type": "input", "name": "bonus", "id": "bns1"}],
                }
            ],
        },
    ],
}


class TestValidateCharacterValues:
    def test_accepts_values_in_every_kind_of_scope(self):
        validate_character_values(
            {
                "hp1": 10,
                "tot1": 10,
                "not1": "header field, root scope",
                "cls1": [{"lvl1": 3}, None, {}],
                "sts1": {"str1": {"scr1": 16}, "dex1": None},
                "svs1": {"frt1": {"bns1": 2}},
            },
            LAYOUT,
            stored=None,
        )

    def test_accepts_a_null_repeater_or_grid(self):
        validate_character_values({"cls1": None, "sts1": None}, LAYOUT, stored=None)

    def test_falls_back_to_the_name_for_a_field_without_an_id(self):
        layout = {"elements": [{"type": "input", "name": "hp"}]}

        validate_character_values({"hp": 10}, layout, stored=None)

    @pytest.mark.parametrize(
        ("values", "message"),
        [
            ({"nope": 1}, "Unknown field id 'nope' in values"),
            ({"lvl1": 1}, "Unknown field id 'lvl1' in values"),
            ({"cls1": [{"hp1": 1}]}, "Unknown field id 'hp1' in values.cls1[0]"),
            ({"sts1": {"con1": {}}}, "Unknown grid row id 'con1' in values.sts1"),
            (
                {"svs1": {"frt1": {"scr1": 1}}},
                "Unknown field id 'scr1' in values.svs1.frt1",
            ),
        ],
        ids=["root", "row-field-at-root", "root-field-in-row", "grid-row", "grid"],
    )
    def test_rejects_keys_the_sheet_doesnt_define_in_that_scope(self, values, message):
        with pytest.raises(ValidationError, match=re.escape(message)):
            validate_character_values(values, LAYOUT, stored=None)

    @pytest.mark.parametrize(
        ("values", "message"),
        [
            ({"cls1": {"lvl1": 1}}, "must be a list of rows"),
            ({"cls1": [3]}, r"values\.cls1\[0\] must be an object"),
            ({"sts1": [1]}, "must be an object of rows"),
            ({"sts1": {"str1": 16}}, r"values\.sts1\.str1 must be an object"),
        ],
        ids=["repeater", "repeater-row", "grid", "grid-row"],
    )
    def test_rejects_containers_of_the_wrong_shape(self, values, message):
        with pytest.raises(ValidationError, match=message):
            validate_character_values(values, LAYOUT, stored=None)

    def test_keeps_keys_already_stored_at_the_same_spot(self):
        stored = {
            "old1": {"anything": 1},
            "cls1": [{}, {"oldlvl": 2}],
            "sts1": {"oldrow": {"scr1": 1}},
        }

        validate_character_values(
            {
                "old1": {"anything": 2},
                # A removed row shifts the rest down, so any stored row counts.
                "cls1": [{"oldlvl": 2}],
                "sts1": {"oldrow": {"scr1": 1}},
            },
            LAYOUT,
            stored=stored,
        )

    def test_a_stored_key_only_counts_where_it_was_stored(self):
        with pytest.raises(ValidationError, match="Unknown field id 'old1'"):
            validate_character_values(
                {"cls1": [{"old1": 1}]}, LAYOUT, stored={"old1": 1}
            )


class TestHiddenValues:
    def test_lists_filled_fields_the_target_drops(self):
        # Drops `hp`, the `classes` repeater, the `stats.dex` row and the
        # `saves.fort.bonus` field.
        target = {
            "schema_version": 1,
            "elements": [
                LAYOUT["elements"][1],
                {
                    **LAYOUT["elements"][3],
                    "items": [{"key": "str", "label": "STR", "id": "str1"}],
                },
                {
                    **LAYOUT["elements"][4],
                    "content": [{"type": "grid_row", "key": "fort", "id": "frt1"}],
                },
            ],
        }
        values = {
            "hp1": 10,
            # Reported as the repeater, not field by field.
            "cls1": [{"lvl1": 3}],
            "sts1": {"str1": {"scr1": 15}, "dex1": {"scr1": 12}},
            # Empty, so nothing is lost.
            "svs1": {"frt1": {"bns1": ""}},
            # Already hidden: the current layout doesn't have it either.
            "old1": 5,
        }

        assert hidden_values(values, LAYOUT, target) == [
            ("cls1", "classes"),
            ("hp1", "hp"),
            ("dex1", "stats.dex"),
        ]
