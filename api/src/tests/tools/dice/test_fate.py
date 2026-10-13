import pytest

from app.tools.dice.fate import FateRoll


class TestFateRollParsing:
    @pytest.mark.parametrize("count", [0, 101])
    def test_rejects_a_dice_count_outside_1_to_100(self, count):
        roll = FateRoll()

        with pytest.raises(ValueError, match="Invalid dice count"):
            roll.new_roll(str(count))


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
