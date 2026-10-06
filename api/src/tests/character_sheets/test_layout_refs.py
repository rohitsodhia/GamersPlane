import re

import pytest

from app.character_sheets.layout_refs import validate_layout_refs
from app.exceptions import ValidationError


def _layout(*elements):
    return {"schema_version": 1, "elements": list(elements)}


def _computed(ref):
    return {"type": "text", "name": "out", "formula": {"ref": ref}}


# Mirrors the frontend's `refs.test.ts` fixture.
_ROOT_FIELDS = [
    {"type": "input", "name": "hp"},
    {
        "type": "grid",
        "name": "stats",
        "items": [{"key": "str", "label": "STR"}, {"key": "dex", "label": "DEX"}],
        "row": [{"type": "input", "name": "score"}],
    },
    {
        "type": "grid",
        "name": "saves",
        "content": [
            {
                "type": "grid_row",
                "key": "fort",
                "content": [{"type": "input", "name": "bonus"}],
            }
        ],
    },
    {
        "type": "repeater",
        "name": "classes",
        "content": [{"type": "input", "name": "level"}],
    },
]


def _root_with(*elements):
    return _layout(*_ROOT_FIELDS, *elements)


def _in_repeater_row(*elements):
    return _layout(
        {"type": "input", "name": "hp"},
        {
            "type": "repeater",
            "name": "classes",
            "content": [
                {"type": "input", "name": "level"},
                {
                    "type": "grid",
                    "name": "sub",
                    "items": [{"key": "a", "label": "A"}],
                    "row": [{"type": "input", "name": "x"}],
                },
                *elements,
            ],
        },
    )


def _in_loop(loop, *elements):
    return _layout({"type": "input", "name": "hp"}, {**loop, "content": list(elements)})


class TestValidateLayoutRefs:
    @pytest.mark.parametrize(
        "ref", ["hp", "stats.dex.score", "saves.fort.bonus"], ids=str
    )
    def test_accepts_absolute_paths_to_a_scalar(self, ref):
        validate_layout_refs(_root_with(_computed(ref)))

    @pytest.mark.parametrize(
        ("ref", "reason"),
        [
            ("nope", "no field named 'nope' at the sheet root"),
            ("stats", "'stats' is a grid; name a row and a field"),
            ("stats.str", "'stats.str' is a grid row"),
            ("stats.con.score", "grid 'stats' has no row 'con'"),
            ("stats.str.nope", "no field named 'nope' in row 'str' of grid 'stats'"),
            ("classes", "'classes' is a repeater"),
            ("classes.0.level", "'classes' is a repeater"),
            ("hp.x", "'hp' is a single field"),
            ("stats..score", "empty segment"),
            ("$foo", "'$foo' isn't a known '$' ref"),
        ],
        ids=lambda v: v if isinstance(v, str) and " " not in v else "",
    )
    def test_rejects_refs_that_dont_end_on_a_scalar(self, ref, reason):
        with pytest.raises(ValidationError, match=re.escape(reason)):
            validate_layout_refs(_root_with(_computed(ref)))

    def test_reports_where_the_bad_ref_is(self):
        with pytest.raises(
            ValidationError,
            match=r"Ref 'nope' at elements\[1\]\.content\[0\]\.formula\.args\[1\]",
        ):
            validate_layout_refs(
                _layout(
                    {"type": "input", "name": "hp"},
                    {
                        "type": "section",
                        "content": [
                            {
                                "type": "text",
                                "name": "out",
                                "formula": {
                                    "op": "+",
                                    "args": [{"ref": "hp"}, {"ref": "nope"}],
                                },
                            }
                        ],
                    },
                )
            )

    def test_rejects_a_ref_that_isnt_a_string(self):
        with pytest.raises(ValidationError, match="must be a string"):
            validate_layout_refs(_root_with(_computed(3)))

    def test_single_segment_means_root_even_inside_a_row(self):
        validate_layout_refs(_in_repeater_row(_computed("hp")))

        with pytest.raises(ValidationError, match=r"use '\$row\.level'"):
            validate_layout_refs(_in_repeater_row(_computed("level")))

    def test_accepts_row_refs_inside_a_row(self):
        validate_layout_refs(
            _in_repeater_row(_computed("$row.level"), _computed("$row.sub.a.x"))
        )

    def test_accepts_row_refs_in_both_grid_forms(self):
        validate_layout_refs(
            _layout(
                {
                    "type": "grid",
                    "name": "stats",
                    "items": [{"key": "str", "label": "STR"}],
                    "row": [
                        {"type": "input", "name": "score"},
                        _computed("$row.score"),
                    ],
                },
                {
                    "type": "grid",
                    "name": "saves",
                    "content": [
                        {
                            "type": "grid_row",
                            "key": "fort",
                            "content": [
                                {"type": "input", "name": "bonus"},
                                _computed("$row.bonus"),
                            ],
                        }
                    ],
                },
            )
        )

    def test_rejects_row_refs_outside_a_row(self):
        with pytest.raises(ValidationError, match="only available inside a repeater"):
            validate_layout_refs(_root_with(_computed("$row.hp")))

    def test_repeater_header_is_outside_the_row(self):
        with pytest.raises(ValidationError, match="only available inside a repeater"):
            validate_layout_refs(
                _layout(
                    {
                        "type": "repeater",
                        "name": "classes",
                        "header": [_computed("$row.level")],
                        "content": [{"type": "input", "name": "level"}],
                    }
                )
            )

    def test_rejects_bare_row(self):
        with pytest.raises(ValidationError, match="name a field after"):
            validate_layout_refs(_in_repeater_row(_computed("$row")))

    def test_accepts_index_and_item_keys_inside_a_loop(self):
        validate_layout_refs(
            _in_loop(
                {"type": "loop", "items": [{"label": "A"}, {"label": "B", "cost": 2}]},
                _computed("$index"),
                _computed("$item.label"),
                _computed("$item.cost"),
            )
        )

    def test_loop_styling_sees_the_loop_but_count_does_not(self):
        validate_layout_refs(
            _layout(
                {"type": "input", "name": "hp"},
                {
                    "type": "loop",
                    "count": {"ref": "hp"},
                    "class_when": {"char-sheet-filled": {"ref": "$index"}},
                    "content": [],
                },
            )
        )

        with pytest.raises(
            ValidationError, match=r"\.count.*only available inside a loop"
        ):
            validate_layout_refs(
                _layout({"type": "loop", "count": {"ref": "$index"}, "content": []})
            )

    @pytest.mark.parametrize(
        ("layout", "reason"),
        [
            (_root_with(_computed("$index")), "only available inside a loop"),
            (
                _in_loop({"type": "loop", "count": 3}, _computed("$item.label")),
                "uses 'count'",
            ),
            (
                _in_loop(
                    {"type": "loop", "items": [{"label": "A"}]}, _computed("$item.cost")
                ),
                "has a 'cost' key",
            ),
        ],
        ids=["index-outside-loop", "item-in-count-loop", "unknown-item-key"],
    )
    def test_rejects_loop_refs_without_a_matching_loop(self, layout, reason):
        with pytest.raises(ValidationError, match=reason):
            validate_layout_refs(layout)

    def test_checks_conditional_styling(self):
        with pytest.raises(ValidationError, match=r"style_when\[0\]\.when"):
            validate_layout_refs(
                _layout(
                    {
                        "type": "section",
                        "style_when": [{"when": {"ref": "nope"}, "styles": {}}],
                        "content": [],
                    }
                )
            )

    def test_checks_both_halves_of_a_set_button(self):
        def button(set_ref, to):
            return {
                "type": "button",
                "label": "x",
                "on_click": {"set": set_ref, "to": to},
            }

        validate_layout_refs(_root_with(button("hp", {"ref": "stats.str.score"})))

        with pytest.raises(ValidationError, match=r"on_click\.set"):
            validate_layout_refs(_root_with(button("nope", 1)))
        with pytest.raises(ValidationError, match=r"on_click\.to"):
            validate_layout_refs(_root_with(button("hp", {"ref": "nope"})))

    def test_a_button_cannot_set_a_loop_value(self):
        with pytest.raises(ValidationError, match="can only set a field"):
            validate_layout_refs(
                _in_loop(
                    {"type": "loop", "count": 3},
                    {
                        "type": "button",
                        "label": "x",
                        "on_click": {"set": "$index", "to": 1},
                    },
                )
            )


# Root fields plus one of each kind of field a `$(...)` can point at.
def _dynamic_root(*elements):
    return _root_with(
        {
            "type": "select",
            "name": "pick",
            "values": ["str", {"value": "dex", "label": "Dex"}, ""],
        },
        {"type": "input", "name": "note"},
        {"type": "checkbox", "name": "flag"},
        {"type": "text", "name": "total", "formula": 1},
        {"type": "select", "name": "empty", "values": [""]},
        *elements,
    )


class TestDynamicRefs:
    def test_accepts_a_select_whose_every_option_names_a_row(self):
        # `pick` also has a blank option, which is exempt.
        validate_layout_refs(_dynamic_root(_computed("stats.$(pick).score")))

    def test_a_dynamic_first_segment_names_a_root_field(self):
        validate_layout_refs(
            _layout(
                {"type": "select", "name": "pick", "values": ["hp", "ac"]},
                {"type": "input", "name": "hp"},
                {"type": "input", "name": "ac"},
                _computed("$(pick)"),
            )
        )

    def test_rejects_a_select_option_that_doesnt_resolve(self):
        # The bad option is a `{value, label}` pair whose label *would*
        # resolve, so this only fails if its value is what's checked.
        layout = _dynamic_root(
            {
                "type": "select",
                "name": "save",
                "values": ["fort", {"value": "will", "label": "fort"}],
            },
            _computed("saves.$(save).bonus"),
        )

        with pytest.raises(
            ValidationError,
            match=re.escape("when 'save' is 'will': grid 'saves' has no row 'will'"),
        ):
            validate_layout_refs(layout)

    def test_checks_every_pairing_of_two_dynamic_segments(self):
        def with_fields(*fields):
            return _dynamic_root(
                {"type": "select", "name": "field", "values": list(fields)},
                _computed("stats.$(pick).$(field)"),
            )

        validate_layout_refs(with_fields("score"))

        with pytest.raises(
            ValidationError,
            match=re.escape(
                "when 'pick' is 'str' and 'field' is 'nope': "
                "there's no field named 'nope' in row 'str' of grid 'stats'"
            ),
        ):
            validate_layout_refs(with_fields("score", "nope"))

    def test_a_dynamic_segment_after_row_names_a_field_in_the_row(self):
        def in_row(options, ref):
            return _in_repeater_row(
                {"type": "select", "name": "which", "values": options},
                _computed(ref),
            )

        validate_layout_refs(in_row(["level"], "$row.$($row.which)"))
        validate_layout_refs(in_row(["a"], "$row.sub.$($row.which).x"))

        # `hp` is a root field, not one of the row's.
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "when '$row.which' is 'hp': there's no field named 'hp' in this row"
            ),
        ):
            validate_layout_refs(in_row(["hp"], "$row.$($row.which)"))

    def test_resolves_the_inner_ref_from_the_current_row(self):
        validate_layout_refs(
            _layout(
                *_ROOT_FIELDS,
                {
                    "type": "repeater",
                    "name": "attacks",
                    "content": [
                        {"type": "select", "name": "stat", "values": ["str", "dex"]},
                        _computed("stats.$($row.stat).score"),
                    ],
                },
            )
        )

    def test_uses_each_loop_items_value(self):
        def loop_over(*stats):
            return _layout(
                *_ROOT_FIELDS,
                {
                    "type": "loop",
                    "items": [{"stat": stat} for stat in stats],
                    "content": [_computed("stats.$($item.stat).score")],
                },
            )

        validate_layout_refs(loop_over("str", "dex"))

        with pytest.raises(ValidationError, match=r"when '\$item\.stat' is 'wis'"):
            validate_layout_refs(loop_over("str", "wis"))
        with pytest.raises(ValidationError, match="no 'stat' in the enclosing loop"):
            validate_layout_refs(loop_over(3, ""))

    def test_free_text_only_checks_the_path_up_to_it(self):
        validate_layout_refs(_dynamic_root(_computed("stats.$(note).anything")))
        validate_layout_refs(_dynamic_root(_computed("$(note).anything")))

        with pytest.raises(ValidationError, match="no field named 'nope'"):
            validate_layout_refs(_dynamic_root(_computed("nope.$(note).score")))

    @pytest.mark.parametrize(
        ("inner", "reason"),
        [
            ("nope", "in '$(nope)': there's no field named 'nope'"),
            ("flag", "'flag' is a checkbox"),
            ("total", "'total' is a computed value"),
            ("empty", "'empty' has no options"),
        ],
        ids=["unresolved", "checkbox", "computed", "no-options"],
    )
    def test_rejects_an_inner_ref_that_cant_hold_a_name(self, inner, reason):
        with pytest.raises(ValidationError, match=re.escape(reason)):
            validate_layout_refs(_dynamic_root(_computed(f"stats.$({inner}).score")))

    def test_rejects_index_as_an_inner_ref(self):
        with pytest.raises(ValidationError, match="'\\$index' is a number"):
            validate_layout_refs(
                _in_loop({"type": "loop", "count": 2}, _computed("$($index)"))
            )

    @pytest.mark.parametrize(
        ("ref", "reason"),
        [
            ("stats.$(pick", "never closed"),
            ("stats.$().score", "'$()' is empty"),
            ("$(a.$(b))", "can't be nested"),
            ("stats.$(pick)x.score", "must be a whole segment"),
            ("stats.x$(pick).score", "must be a whole segment"),
        ],
        ids=["unclosed", "empty", "nested", "trailing", "leading"],
    )
    def test_rejects_a_malformed_dynamic_segment(self, ref, reason):
        with pytest.raises(ValidationError, match=re.escape(reason)):
            validate_layout_refs(_dynamic_root(_computed(ref)))
