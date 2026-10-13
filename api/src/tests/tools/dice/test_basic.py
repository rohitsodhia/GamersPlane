import pytest

from app.tools.dice.basic import BasicDie, BasicRoll


class TestBasicDie:
    @pytest.mark.parametrize("sides", [1, 1001])
    def test_rejects_sides_outside_2_to_1000(self, sides):
        with pytest.raises(ValueError, match="Invalid die sides"):
            BasicDie(sides)

    def test_accepts_the_max_sides(self):
        assert BasicDie(1000).sides == 1000


class TestBasicRollParsing:
    def test_defaults_count_to_one_when_omitted(self):
        roll = BasicRoll()
        roll.new_roll("d20")

        assert roll._groups[0].terms[0].count == 1

    @pytest.mark.parametrize(("expression", "modifier"), [("+5", 5), ("-3", -3)])
    def test_flat_modifier_only(self, expression, modifier):
        roll = BasicRoll()
        roll.new_roll(expression)

        group = roll._groups[0]
        assert group.terms == []
        assert group.modifier == modifier

    def test_dice_and_modifier_combined(self):
        roll = BasicRoll()
        roll.new_roll("2d6+3")

        group = roll._groups[0]
        assert group.expression == "2d6+3"
        assert len(group.terms) == 1
        assert group.terms[0].count == 2
        assert group.terms[0].sides == 6
        assert group.terms[0].sign == 1
        assert group.modifier == 3

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

    def test_empty_string_produces_no_groups(self):
        roll = BasicRoll()
        roll.new_roll("")

        assert roll._groups == []

    @pytest.mark.parametrize("expression", ["0d6", "101d6", "1d1001"])
    def test_rejects_out_of_range_dice_counts_and_sides(self, expression):
        roll = BasicRoll()

        with pytest.raises(ValueError):
            roll.new_roll(expression)

    def test_accepts_the_max_dice_count_and_sides(self):
        roll = BasicRoll()
        roll.new_roll("100d1000")

        assert roll._groups[0].terms[0].count == 100

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
        assert sorted(term.dropped) == [0, 2]  # the 6 and the 5
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
