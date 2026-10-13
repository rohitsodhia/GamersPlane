import pytest

from app.character_sheets.roll_template import (
    TemplateSyntaxError,
    has_single_d20,
    normalize_dice,
    parse_template,
    template_refs,
)


class TestParseTemplate:
    def test_splits_text_and_refs(self):
        assert parse_template("1d20+${str_mod} x") == [
            ("text", "1d20+"),
            ("ref", "str_mod"),
            ("text", " x"),
        ]

    def test_keeps_a_dynamic_ref_with_its_parens_and_dots_whole(self):
        assert template_refs("${stats.$(pick).mod}${$row.bonus}") == [
            "stats.$(pick).mod",
            "$row.bonus",
        ]

    @pytest.mark.parametrize("template", ["1d${x", "1d${stats.$(pick}", "1d${ }"])
    def test_rejects_an_unterminated_or_empty_placeholder(self, template):
        with pytest.raises(TemplateSyntaxError):
            parse_template(template)


class TestNormalizeDice:
    @pytest.mark.parametrize(
        ("dice", "expected"),
        [
            ("1d20+-3", "1d20-3"),
            ("1d20-+3", "1d20-3"),
            ("1d20--3", "1d20+3"),
            ("1d20++3", "1d20+3"),
            ("1d20 + 5", "1d20+5"),
            ("1d20+0", "1d20"),
            ("1d20+-0", "1d20"),
            ("1d20+0,1d6-0", "1d20,1d6"),
            ("+1d20", "1d20"),
            ("1d6,+1d4", "1d6,1d4"),
            ("1d20+0d6", "1d20+0d6"),
            ("1d10+10", "1d10+10"),
        ],
    )
    def test_tidies_signs_and_zero_modifiers(self, dice, expected):
        assert normalize_dice(dice) == expected


class TestHasSingleD20:
    @pytest.mark.parametrize("dice", ["1d20", "d20+5", "1d6,1d20", "1D20"])
    def test_finds_a_single_d20(self, dice):
        assert has_single_d20(dice)

    @pytest.mark.parametrize("dice", ["2d20", "1d200", "1d20h1", "1d6"])
    def test_ignores_anything_else(self, dice):
        assert not has_single_d20(dice)
