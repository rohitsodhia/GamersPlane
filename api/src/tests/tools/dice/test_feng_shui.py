import pytest

from app.tools.dice.feng_shui import FengShuiRoll


class TestFengShuiRollParsing:
    def test_raises_for_unknown_type(self):
        roll = FengShuiRoll()

        with pytest.raises(ValueError):
            roll.new_roll("5", roll_type="nonsense")

    def test_sets_action_value(self):
        roll = FengShuiRoll()
        roll.new_roll("8", roll_type="standard")

        assert roll.action_value == 8

    def test_clamps_negative_action_value_to_zero(self):
        roll = FengShuiRoll()
        roll.new_roll("-8", roll_type="standard")

        assert roll.action_value == 0

    def test_defaults_to_standard_type(self):
        roll = FengShuiRoll()
        roll.new_roll("5")

        assert roll.type == "standard"


class TestFengShuiRollRolling:
    def test_standard_roll_takes_one_die_each_when_not_exploding(self, monkeypatch):
        values = iter([3, 2])
        monkeypatch.setattr(
            "app.tools.dice.basic.random.randint", lambda a, b: next(values)
        )
        roll = FengShuiRoll()
        roll.new_roll("5", roll_type="standard")
        result = roll.roll()

        assert result.positive == [3]
        assert result.negative == [2]
        assert result.extra is None

    def test_standard_roll_explodes_on_six(self, monkeypatch):
        values = iter([6, 4, 2])
        monkeypatch.setattr(
            "app.tools.dice.basic.random.randint", lambda a, b: next(values)
        )
        roll = FengShuiRoll()
        roll.new_roll("5", roll_type="standard")
        result = roll.roll()

        assert result.positive == [6, 4]
        assert result.negative == [2]

    def test_fortune_roll_adds_an_extra_die(self, monkeypatch):
        values = iter([3, 2, 5])
        monkeypatch.setattr(
            "app.tools.dice.basic.random.randint", lambda a, b: next(values)
        )
        roll = FengShuiRoll()
        roll.new_roll("5", roll_type="fortune")
        result = roll.roll()

        assert result.extra == 5

    def test_closed_roll_does_not_explode_on_six(self, monkeypatch):
        monkeypatch.setattr("app.tools.dice.basic.random.randint", lambda a, b: 6)
        roll = FengShuiRoll()
        roll.new_roll("5", roll_type="closed")
        result = roll.roll()

        assert result.positive == [6]
        assert result.negative == [6]

    def test_total_combines_action_value_positive_negative_and_extra(self, monkeypatch):
        values = iter([3, 2, 1])
        monkeypatch.setattr(
            "app.tools.dice.basic.random.randint", lambda a, b: next(values)
        )
        roll = FengShuiRoll()
        roll.new_roll("5", roll_type="fortune")
        result = roll.roll()

        assert result.total == 5 + 3 - 2 + 1
