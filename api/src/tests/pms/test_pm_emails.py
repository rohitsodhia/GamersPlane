import logging
import pytest

from app.configs import configs
from app.models import UserMeta
from app.pms import functions as pm_functions
from tests.factories import ActivatedUserFactory, PMFactory, prose_doc


@pytest.fixture(autouse=True)
def _enable_pm_logger(monkeypatch):
    # Alembic's fileConfig (run by the test DB setup) disables loggers that
    # already existed at import time, which would hide our log records.
    monkeypatch.setattr(pm_functions.logger, "disabled", False)


@pytest.fixture
def sent(monkeypatch):
    monkeypatch.setattr(configs, "EMAIL_ENABLED", True)
    calls = []

    async def fake_send_email(to, subject, content, **kwargs):
        calls.append({"to": to, "subject": subject, "content": content, **kwargs})

    monkeypatch.setattr(pm_functions, "send_email", fake_send_email)
    return calls


@pytest.fixture
def set_pref(db_session):
    async def _set(user, value):
        db_session.add(
            UserMeta(user_id=user.id, key=UserMeta.MetaKeys.PM_MAIL.value, value=value)
        )
        await db_session.flush()

    return _set


def _payload(username, **overrides):
    return {
        "username": username,
        "title": "Hello",
        "message": prose_doc("Hi there"),
        **overrides,
    }


class TestSendPMEmail:
    async def test_recipient_is_emailed_and_sender_is_not(
        self, authed_client, create, sent
    ):
        client, user = authed_client
        recipient = await create(ActivatedUserFactory)

        response = await client.post("/pms", json=_payload(recipient.username))

        assert response.status_code == 200
        assert [call["to"] for call in sent] == [recipient.email]
        assert sent[0]["subject"] == f"New message from {user.username}"
        assert "Hi there" in sent[0]["content"]

    async def test_link_points_at_the_new_pm(self, authed_client, create, sent):
        client, _user = authed_client
        recipient = await create(ActivatedUserFactory)

        await client.post("/pms", json=_payload(recipient.username))

        listing = await client.get("/pms", params={"box": "outbox"})
        pm_id = listing.json()["pms"][0]["id"]
        assert f'href="{configs.HOST_NAME}/pms/{pm_id}"' in sent[0]["content"]

    async def test_pm_mail_off_sends_nothing(
        self, authed_client, create, set_pref, sent
    ):
        client, _user = authed_client
        recipient = await create(ActivatedUserFactory)
        await set_pref(recipient, False)

        response = await client.post("/pms", json=_payload(recipient.username))

        assert response.status_code == 200
        assert sent == []

    async def test_reply_emails_the_other_party(self, authed_client, create, sent):
        client, user = authed_client
        other = await create(ActivatedUserFactory)
        original = await create(PMFactory, recipient=user, sender=other)

        response = await client.post(
            "/pms", json=_payload(other.username, reply_to_id=original.id)
        )

        assert response.status_code == 200
        assert [call["to"] for call in sent] == [other.email]
        assert sent[0]["subject"] == f"New message from {user.username}"

    @pytest.mark.parametrize("target", ["self", "nobody"])
    async def test_rejected_pm_sends_nothing(self, authed_client, sent, target):
        client, user = authed_client

        response = await client.post(
            "/pms", json=_payload(user.username if target == "self" else target)
        )

        assert response.status_code == 400
        assert sent == []

    async def test_email_disabled_sends_nothing_and_logs(
        self, authed_client, create, sent, monkeypatch, caplog
    ):
        client, _user = authed_client
        recipient = await create(ActivatedUserFactory)
        monkeypatch.setattr(configs, "EMAIL_ENABLED", False)

        with caplog.at_level(logging.INFO, logger=pm_functions.logger.name):
            response = await client.post("/pms", json=_payload(recipient.username))

        assert response.status_code == 200
        assert sent == []
        assert "would have mailed PM" in caplog.text
        assert f"to user {recipient.id}" in caplog.text
