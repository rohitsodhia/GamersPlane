import string

from app.util import random_alpha_num


class TestRandomAlphaNum:
    def test_only_uses_alpha_num_characters(self):
        allowed = set(string.ascii_letters + string.digits)
        result = random_alpha_num(200)

        assert len(result) == 200
        assert set(result) <= allowed
