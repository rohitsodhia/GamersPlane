import pytest

from app.tools.dice.star_wars_ffg import DICE_FACES, StarWarsFFGDie, StarWarsFFGRoll


class TestStarWarsFFGDie:
    def test_raises_for_unknown_die_type(self):
        with pytest.raises(ValueError):
            StarWarsFFGDie("nonsense")

    def test_sides_matches_face_count(self):
        die = StarWarsFFGDie("proficiency")

        assert die.sides == len(DICE_FACES["proficiency"])

    def test_roll_returns_face_at_rolled_index(self, monkeypatch):
        monkeypatch.setattr(
            "app.tools.dice.star_wars_ffg.random.randint", lambda a, b: 3
        )
        die = StarWarsFFGDie("ability")

        assert die.roll() == DICE_FACES["ability"][3]


class TestStarWarsFFGRollParsing:
    def test_expands_shorthand_letters(self):
        roll = StarWarsFFGRoll()
        roll.new_roll("a p b")

        assert roll._dice_names == ["ability", "proficiency", "boost"]

    def test_accepts_full_names_case_insensitively(self):
        roll = StarWarsFFGRoll()
        roll.new_roll("Ability PROFICIENCY")

        assert roll._dice_names == ["ability", "proficiency"]

    def test_ignores_unrecognized_tokens(self):
        roll = StarWarsFFGRoll()
        roll.new_roll("a xyz p")

        assert roll._dice_names == ["ability", "proficiency"]

    def test_repeated_letters_produce_multiple_dice(self):
        roll = StarWarsFFGRoll()
        roll.new_roll("a a a")

        assert roll._dice_names == ["ability", "ability", "ability"]

    def test_adjacent_letters_with_no_separator_are_one_token_and_skipped(self):
        roll = StarWarsFFGRoll()
        roll.new_roll("aaa")

        assert roll._dice_names == []

    def test_reuses_die_instance_per_type(self):
        roll = StarWarsFFGRoll()
        roll.new_roll("a a")

        assert len(roll._dice) == 1


class TestStarWarsFFGRollRolling:
    def test_splits_multi_icon_results_into_totals(self, monkeypatch):
        # index 4 on the ability die is "success_success"
        monkeypatch.setattr(
            "app.tools.dice.star_wars_ffg.random.randint", lambda a, b: 4
        )
        roll = StarWarsFFGRoll()
        roll.new_roll("a")
        result = roll.roll()

        assert result.rolls[0].result == "success_success"
        assert result.totals["success"] == 2

    def test_blank_faces_do_not_add_to_totals(self, monkeypatch):
        # index 0 on the ability die is a blank face
        monkeypatch.setattr(
            "app.tools.dice.star_wars_ffg.random.randint", lambda a, b: 0
        )
        roll = StarWarsFFGRoll()
        roll.new_roll("a")
        result = roll.roll()

        assert result.rolls[0].result == ""
        assert sum(result.totals.values()) == 0

    def test_net_success_and_advantage(self, monkeypatch):
        # ability index 1 = "success", difficulty index 2 = "threat"
        values = iter([1, 2])
        monkeypatch.setattr(
            "app.tools.dice.star_wars_ffg.random.randint", lambda a, b: next(values)
        )
        roll = StarWarsFFGRoll()
        roll.new_roll("a d")
        result = roll.roll()

        assert result.net_success == 1
        assert result.net_advantage == -1
