import pytest

from app.exceptions import ValidationError
from app.models import UserMeta


class TestValueGetter:
    def test_casts_bool_key(self):
        meta = UserMeta(key=UserMeta.MetaKeys.GM_MAIL.value, value=True)

        assert meta.value is True

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

    def test_bool_true_stored_as_string_one(self):
        meta = UserMeta(key=UserMeta.MetaKeys.GM_MAIL.value)

        meta.value = True

        assert meta._value == "1"

    def test_bool_false_stored_as_string_zero(self):
        meta = UserMeta(key=UserMeta.MetaKeys.GM_MAIL.value)

        meta.value = False

        assert meta._value == "0"

    def test_post_side_lowercases_value(self):
        meta = UserMeta(key=UserMeta.MetaKeys.POST_SIDE.value)

        meta.value = "L"

        assert meta.value == "l"

    def test_post_side_invalid_value_raises_validation_error(self):
        meta = UserMeta(key=UserMeta.MetaKeys.POST_SIDE.value)

        with pytest.raises(ValidationError):
            meta.value = "x"

    def test_no_key_set_raises_value_error(self):
        meta = UserMeta()

        with pytest.raises(ValueError):
            meta.value = "foo"

    def test_invalid_key_raises_value_error(self):
        meta = UserMeta(key="not-a-real-key")

        with pytest.raises(ValueError):
            meta.value = "foo"
