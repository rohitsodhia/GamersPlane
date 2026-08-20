import pytest

from app.tools.dice.basic import BasicRoll
from app.tools.dice.fate import FateRoll
from app.tools.dice.feng_shui import FengShuiRoll
from app.tools.dice.registry import get_roll
from app.tools.dice.star_wars_ffg import StarWarsFFGRoll


class TestGetRoll:
    def test_raises_for_unknown_system(self):
        with pytest.raises(ValueError):
            get_roll("nonsense", "1d6")

    @pytest.mark.parametrize(
        ("system", "roll_string", "options", "roll_cls"),
        [
            ("basic", "1d6", {}, BasicRoll),
            ("fate", "4", {}, FateRoll),
            ("fengshui", "5", {"roll_type": "standard"}, FengShuiRoll),
            ("starwarsffg", "a p", {}, StarWarsFFGRoll),
        ],
    )
    def test_returns_correct_roll_type_with_result_populated(
        self, system, roll_string, options, roll_cls
    ):
        roll = get_roll(system, roll_string, **options)

        assert isinstance(roll, roll_cls)
        assert roll.result is not None
