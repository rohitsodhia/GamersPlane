import pytest

from app.tools.dice.fate import FateRoll


class TestFateRollParsing:
    def test_sets_num_dice(self):
        roll = FateRoll()
        roll.new_roll("4")

        assert roll.num_dice == 4

    @pytest.mark.parametrize("count", [0, -4])
    def test_raises_for_fewer_than_one_die(self, count):
        roll = FateRoll()

        with pytest.raises(ValueError):
            roll.new_roll(str(count))

    def test_defaults_modifier_to_zero(self):
        roll = FateRoll()
        roll.new_roll("4")

        assert roll.modifier == 0

    def test_sets_modifier(self):
        roll = FateRoll()
        roll.new_roll("4", modifier=2)

        assert roll.modifier == 2


class TestFateRollRolling:
    def test_rolls_map_to_faces_and_are_counted(self, monkeypatch):
        values = iter([1, 1, 2, 3, 3])
        monkeypatch.setattr(
            "app.tools.dice.fate.random.randint", lambda a, b: next(values)
        )
        roll = FateRoll()
        roll.new_roll("5")
        result = roll.roll()

        assert result.rolls == [-1, -1, 0, 1, 1]
        assert result.negative == 2
        assert result.blank == 1
        assert result.positive == 2

    def test_total_includes_modifier(self, monkeypatch):
        values = iter([3, 3, 1])
        monkeypatch.setattr(
            "app.tools.dice.fate.random.randint", lambda a, b: next(values)
        )
        roll = FateRoll()
        roll.new_roll("3", modifier=1)
        result = roll.roll()

        assert result.total == 2  # (1 + 1 - 1) + 1
