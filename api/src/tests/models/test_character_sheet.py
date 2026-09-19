import pytest

from app.models import CharacterSheet

Status = CharacterSheet.Status


class TestIsPublic:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (Status.PRIVATE, False),
            (Status.PUBLIC, True),
            (Status.OFFICIAL, True),
            (Status.RETIRED, False),
        ],
    )
    def test_is_public(self, status, expected):
        assert CharacterSheet(status=status).is_public is expected
