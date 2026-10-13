import pytest

from app.exceptions import ValidationError
from app.models import UserMeta


class TestValueGetter:
    @pytest.mark.parametrize(("stored", "expected"), [("1", True), ("0", False)])
    def test_casts_bool_key(self, stored, expected):
        meta = UserMeta(key=UserMeta.MetaKeys.GM_MAIL.value)
        meta._value = stored

        assert meta.value is expected

    def test_casts_str_key(self):
        meta = UserMeta(key=UserMeta.MetaKeys.PRONOUNS.value, value="they/them")

        assert meta.value == "they/them"

    def test_invalid_key_returns_none(self):
        meta = UserMeta(key="not-a-real-key")
        meta._value = "ignored"

        assert meta.value is None


class TestValueSetter:
    def test_wrong_type_raises_validation_error(self):
        meta = UserMeta(key=UserMeta.MetaKeys.GM_MAIL.value)

        with pytest.raises(ValidationError):
            meta.value = "not-a-bool"

    @pytest.mark.parametrize(("value", "stored"), [(True, "1"), (False, "0")])
    def test_bool_stored_as_string(self, value, stored):
        meta = UserMeta(key=UserMeta.MetaKeys.GM_MAIL.value)

        meta.value = value

        assert meta._value == stored

    def test_post_side_lowercases_value(self):
        meta = UserMeta(key=UserMeta.MetaKeys.POST_SIDE.value)

        meta.value = "L"

        assert meta.value == "l"

    def test_post_side_invalid_value_raises_validation_error(self):
        meta = UserMeta(key=UserMeta.MetaKeys.POST_SIDE.value)

        with pytest.raises(ValidationError):
            meta.value = "x"

    def test_invalid_key_raises_value_error(self):
        meta = UserMeta(key="not-a-real-key")

        with pytest.raises(ValueError):
            meta.value = "foo"
