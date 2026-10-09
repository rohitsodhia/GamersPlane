import pytest

from app.models import PostDraw, PostRoll
from app.posts.visibility import redact_draw, redact_roll, summarize_roll_result

BASIC_RESULT = {
    "groups": [{"expression": "2d6", "terms": [], "modifier": 0, "total": 7}],
    "total": 7,
}
FFG_RESULT = {
    "rolls": [{"die": "proficiency", "result": "triumph"}],
    "totals": {
        "success": 2,
        "advantage": 1,
        "triumph": 1,
        "failure": 1,
        "threat": 3,
        "despair": 0,
        "whiteDot": 0,
        "blackDot": 0,
    },
    "net_success": 2,
    "net_advantage": -2,
}


def make_roll(roll_type="basic", result=None, **flags):
    return PostRoll(
        id=1,
        post_id=1,
        type=roll_type,
        reason="Attack",
        input="2d6",
        options={"reroll_aces": True},
        result=result or BASIC_RESULT,
        hide_reason=flags.get("hide_reason", False),
        hide_dice=flags.get("hide_dice", False),
        hide_result=flags.get("hide_result", False),
    )


class TestSummarizeRollResult:
    @pytest.mark.parametrize(
        ("roll_type", "result", "expected"),
        [
            ("basic", BASIC_RESULT, {"total": 7}),
            ("fate", {"rolls": [1, 0], "total": 1}, {"total": 1}),
            (
                "fengshui",
                {"positive": [3], "negative": [1], "total": 12},
                {"total": 12},
            ),
            (
                "starwarsffg",
                FFG_RESULT,
                {"net_success": 2, "net_advantage": -2, "triumph": 1, "despair": 0},
            ),
        ],
    )
    def test_only_the_outcome_is_kept(self, roll_type, result, expected):
        assert summarize_roll_result(roll_type, result) == expected


class TestRedactRoll:
    def test_full_view_sees_everything_even_when_flags_are_set(self):
        roll = make_roll(hide_reason=True, hide_dice=True, hide_result=True)

        data = redact_roll(roll, full_view=True)

        assert data.reason == "Attack"
        assert data.input == "2d6"
        assert data.options == {"reroll_aces": True}
        assert data.result == BASIC_RESULT
        assert data.summary is None
        assert (data.hide_reason, data.hide_dice, data.hide_result) == (True,) * 3

    def test_unflagged_roll_is_fully_visible_to_everyone(self):
        data = redact_roll(make_roll(), full_view=False)

        assert data.reason == "Attack"
        assert data.input == "2d6"
        assert data.result == BASIC_RESULT
        assert data.summary is None

    def test_hide_reason_only_withholds_the_reason(self):
        data = redact_roll(make_roll(hide_reason=True), full_view=False)

        assert data.reason is None
        assert data.input == "2d6"
        assert data.result == BASIC_RESULT

    def test_hide_result_keeps_the_input_but_withholds_faces_and_total(self):
        data = redact_roll(make_roll(hide_result=True), full_view=False)

        assert data.input == "2d6"
        assert data.options == {"reroll_aces": True}
        assert data.result is None
        assert data.summary is None

    def test_hide_dice_alone_leaves_reason_and_total_only(self):
        data = redact_roll(make_roll(hide_dice=True), full_view=False)

        assert data.reason == "Attack"
        assert data.input is None
        assert data.options is None
        assert data.result is None
        assert data.summary == {"total": 7}

    def test_hide_dice_and_result_withhold_everything_but_the_reason(self):
        data = redact_roll(make_roll(hide_dice=True, hide_result=True), full_view=False)

        assert data.reason == "Attack"
        assert data.input is None
        assert data.result is None
        assert data.summary is None


class TestRedactDraw:
    def make_draw(self):
        return PostDraw(
            id=1,
            post_id=1,
            deck_id=1,
            deck_label="Deck",
            deck_type="pc",
            reason="Fortune",
            cards=[10, 20, 30],
            revealed=[False, True, False],
        )

    def test_author_sees_every_card(self):
        data = redact_draw(self.make_draw(), is_author=True)

        assert data.cards == [10, 20, 30]
        assert data.revealed == [False, True, False]

    def test_others_see_only_revealed_cards_and_keep_the_list_length(self):
        data = redact_draw(self.make_draw(), is_author=False)

        assert data.cards == [None, 20, None]
        assert data.revealed == [False, True, False]
