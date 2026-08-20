import pytest

from app.tools.dice.basic import BasicDie, BasicRoll


class TestBasicDie:
    @pytest.mark.parametrize("sides", [0, 1, -5])
    def test_raises_for_fewer_than_two_sides(self, sides):
        with pytest.raises(ValueError):
            BasicDie(sides)

    def test_clamps_sides_above_max(self):
        assert BasicDie(5000).sides == 1000


class TestBasicRollParsing:
    def test_single_die_term(self):
        roll = BasicRoll()
        roll.new_roll("1d6")

        group = roll._groups[0]
        assert group.expression == "1d6"
        assert len(group.terms) == 1
        assert group.terms[0].count == 1
        assert group.terms[0].sides == 6
        assert group.terms[0].sign == 1

    def test_defaults_count_to_one_when_omitted(self):
        roll = BasicRoll()
        roll.new_roll("d20")

        assert roll._groups[0].terms[0].count == 1

    def test_flat_modifier_only(self):
        roll = BasicRoll()
        roll.new_roll("+5")

        group = roll._groups[0]
        assert group.terms == []
        assert group.modifier == 5

    def test_negative_flat_modifier(self):
        roll = BasicRoll()
        roll.new_roll("-3")

        assert roll._groups[0].modifier == -3

    def test_dice_and_modifier_combined(self):
        roll = BasicRoll()
        roll.new_roll("2d6+3")

        group = roll._groups[0]
        assert group.terms[0].count == 2
        assert group.terms[0].sides == 6
        assert group.modifier == 3

    def test_negative_dice_term(self):
        roll = BasicRoll()
        roll.new_roll("1d20-1d4")

        terms = roll._groups[0].terms
        assert terms[0].sign == 1
        assert terms[1].sign == -1

    def test_comma_separated_groups(self):
        roll = BasicRoll()
        roll.new_roll("1d20, 2d6+1")

        assert len(roll._groups) == 2
        assert roll._groups[0].expression == "1d20"
        assert roll._groups[1].expression == "2d6+1"

    def test_ignores_spaces(self):
        roll = BasicRoll()
        roll.new_roll(" 2d6 + 1 ")

        assert roll._groups[0].expression == "2d6+1"

    def test_keep_highest_notation(self):
        roll = BasicRoll()
        roll.new_roll("4d6h3")

        term = roll._groups[0].terms[0]
        assert term.keep_high is True
        assert term.keep_count == 3

    def test_keep_lowest_notation(self):
        roll = BasicRoll()
        roll.new_roll("4d6l3")

        term = roll._groups[0].terms[0]
        assert term.keep_high is False
        assert term.keep_count == 3

    def test_empty_string_produces_no_groups(self):
        roll = BasicRoll()
        roll.new_roll("")

        assert roll._groups == []

    def test_invalid_die_sides_raises(self):
        roll = BasicRoll()

        with pytest.raises(ValueError):
            roll.new_roll("1d1")

    def test_zero_dice_count_raises(self):
        roll = BasicRoll()

        with pytest.raises(ValueError):
            roll.new_roll("0d6")

    @pytest.mark.parametrize("expression", ["3d6+4:2l", "2d6x"])
    def test_invalid_syntax_raises(self, expression):
        roll = BasicRoll()

        with pytest.raises(ValueError):
            roll.new_roll(expression)


class TestBasicRollRolling:
    def test_simple_roll_sums_dice_and_modifier(self, monkeypatch):
        monkeypatch.setattr("app.tools.dice.basic.random.randint", lambda a, b: 4)
        roll = BasicRoll()
        roll.new_roll("2d6+3")
        result = roll.roll()

        assert result.groups[0].terms[0].rolls == [4, 4]
        assert result.groups[0].total == 11
        assert result.total == 11

    def test_multiple_groups_sum_independently(self, monkeypatch):
        monkeypatch.setattr("app.tools.dice.basic.random.randint", lambda a, b: 3)
        roll = BasicRoll()
        roll.new_roll("1d6, 1d6+1")
        result = roll.roll()

        assert result.groups[0].total == 3
        assert result.groups[1].total == 4
        assert result.total == 7

    def test_keep_highest_drops_lowest_rolls(self, monkeypatch):
        values = iter([6, 2, 5, 1])
        monkeypatch.setattr(
            "app.tools.dice.basic.random.randint", lambda a, b: next(values)
        )
        roll = BasicRoll()
        roll.new_roll("4d6h3")
        result = roll.roll()

        term = result.groups[0].terms[0]
        assert term.rolls == [6, 2, 5, 1]
        assert term.dropped == [3]  # index of the single lowest roll (1)
        assert term.subtotal == 13  # 6 + 2 + 5

    def test_keep_lowest_drops_highest_rolls(self, monkeypatch):
        values = iter([6, 2, 5, 1])
        monkeypatch.setattr(
            "app.tools.dice.basic.random.randint", lambda a, b: next(values)
        )
        roll = BasicRoll()
        roll.new_roll("4d6l2")
        result = roll.roll()

        term = result.groups[0].terms[0]
        assert term.subtotal == 3  # 2 + 1

    def test_negative_dice_term_subtracts(self, monkeypatch):
        monkeypatch.setattr("app.tools.dice.basic.random.randint", lambda a, b: 4)
        roll = BasicRoll()
        roll.new_roll("1d20-1d4")
        result = roll.roll()

        assert result.groups[0].total == 0

    def test_reroll_aces_chains_exploding_dice(self, monkeypatch):
        values = iter([6, 6, 2])
        monkeypatch.setattr(
            "app.tools.dice.basic.random.randint", lambda a, b: next(values)
        )
        roll = BasicRoll()
        roll.new_roll("1d6", reroll_aces=True)
        result = roll.roll()

        term = result.groups[0].terms[0]
        assert term.rolls == [[6, 6, 2]]
        assert term.subtotal == 14

    def test_without_reroll_aces_max_roll_does_not_chain(self, monkeypatch):
        monkeypatch.setattr("app.tools.dice.basic.random.randint", lambda a, b: 6)
        roll = BasicRoll()
        roll.new_roll("1d6")
        result = roll.roll()

        assert result.groups[0].terms[0].rolls == [6]

    def test_reuses_same_die_instance_for_repeated_sides(self):
        roll = BasicRoll()
        roll.new_roll("1d6, 1d6")

        assert len(roll._dice) == 1
