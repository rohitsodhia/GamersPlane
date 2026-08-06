import datetime

import pytest
from pydantic import ValidationError

from app.me.schemas import UpdateProfileInput


class TestValidateBirthday:
    def test_past_birthday_is_accepted(self):
        UpdateProfileInput(birthday=datetime.date(1990, 1, 1))

    def test_today_is_accepted(self):
        UpdateProfileInput(birthday=datetime.date.today())

    def test_future_birthday_is_rejected(self):
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        with pytest.raises(ValidationError):
            UpdateProfileInput(birthday=tomorrow)
