from unittest.mock import AsyncMock

import pytest

from app.contact import rate_limit


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    rate_limit.reset()
    yield
    rate_limit.reset()


@pytest.fixture
def sent(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr("app.contact.routes.send_email", mock)
    return mock
