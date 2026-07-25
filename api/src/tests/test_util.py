import string

from app.util import random_alpha_num


class TestRandomAlphaNum:
    def test_returns_requested_length(self):
        assert len(random_alpha_num(16)) == 16

    def test_returns_empty_string_for_zero_length(self):
        assert random_alpha_num(0) == ""

    def test_only_uses_alpha_num_characters(self):
        allowed = set(string.ascii_letters + string.digits)
        result = random_alpha_num(200)

        assert set(result) <= allowed

    def test_results_are_not_deterministic(self):
        results = {random_alpha_num(16) for _ in range(20)}

        assert len(results) > 1
