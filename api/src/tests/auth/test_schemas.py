import pytest
from pydantic import ValidationError

from app.auth.schemas import RegisterInput
from app.models import User


def _make(**overrides):
    fields = {
        "email": "test@example.com",
        "username": "validuser",
        "password": "ValidPass1!",
    }
    fields.update(overrides)
    return RegisterInput(**fields)


class TestUsernamePattern:
    @pytest.mark.parametrize(
        "username",
        [
            "ab",
            "a1",
            "a_",
            "Name_1",
            "abc123",
        ],
    )
    def test_valid_usernames_are_accepted(self, username):
        _make(username=username)

    @pytest.mark.parametrize(
        "username",
        [
            "1abc",
            "_abc",
            "a",
            "ab!",
            "ab-cd",
            "ab cd",
        ],
    )
    def test_invalid_usernames_are_rejected(self, username):
        with pytest.raises(ValidationError):
            _make(username=username)


class TestPasswordLength:
    def test_password_at_minimum_length_is_accepted(self):
        _make(password="a" * User.MIN_PASSWORD_LENGTH)

    def test_password_below_minimum_length_is_rejected(self):
        with pytest.raises(ValidationError):
            _make(password="a" * (User.MIN_PASSWORD_LENGTH - 1))
