import pytest

from app.models import Game
from app.models.game import PostFrequency


class TestPostFrequency:
    @pytest.mark.parametrize(
        ("raw", "times_per", "per_period"),
        [
            ("3/w", 3, "w"),
            ("1/d", 1, "d"),
            ("12/w", 12, "w"),
            ("99/w", 99, "w"),
        ],
    )
    def test_getter_parses_valid_value(self, raw, times_per, per_period):
        game = Game(post_frequency=raw)

        assert game.post_frequency == PostFrequency(times_per, per_period)

    def test_str_round_trips_to_raw_format(self):
        assert str(PostFrequency(3, "w")) == "3/w"

    def test_setting_a_post_frequency_instance(self):
        game = Game(post_frequency=PostFrequency(2, "d"))

        assert game.post_frequency == PostFrequency(2, "d")

    def test_changing_value_updates_getter(self):
        game = Game(post_frequency="1/d")

        game.post_frequency = "5/w"

        assert game.post_frequency == PostFrequency(5, "w")

    @pytest.mark.parametrize(
        "invalid",
        [
            "1d",
            "1/x",
            "100/w",
            "123/w",
            "0/w",
            "01/w",
            "3/",
            "3/W",
            "",
        ],
    )
    def test_setter_rejects_invalid_format(self, invalid):
        game = Game()

        with pytest.raises(ValueError, match="post_frequency must match"):
            game.post_frequency = invalid
