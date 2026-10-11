import logging

import aiosmtplib
import pytest

from app.configs import configs
from app.helpers import email as email_module
from app.helpers.email import get_template, send_email


@pytest.fixture(autouse=True)
def _enable_email_logger(monkeypatch):
    # Alembic's fileConfig (run by the test DB setup) disables loggers that
    # already existed at import time, which would hide our log records.
    monkeypatch.setattr(email_module.logger, "disabled", False)


@pytest.fixture
def smtp_calls(monkeypatch):
    calls = []

    async def fake_send(message, **kwargs):
        calls.append((message, kwargs))

    monkeypatch.setattr(email_module.aiosmtplib, "send", fake_send)
    return calls


class TestSendEmail:
    async def test_disabled_logs_and_does_not_send(
        self, monkeypatch, smtp_calls, caplog
    ):
        monkeypatch.setattr(configs, "EMAIL_ENABLED", False)

        with caplog.at_level(logging.INFO, logger=email_module.logger.name):
            await send_email("a@example.com", "Hello subj", "<p>body text</p>")

        assert smtp_calls == []
        assert "a@example.com" in caplog.text
        assert "Hello subj" in caplog.text
        assert "<p>body text</p>" in caplog.text

    async def test_enabled_sends_well_formed_message(self, monkeypatch, smtp_calls):
        monkeypatch.setattr(configs, "EMAIL_ENABLED", True)
        monkeypatch.setattr(configs, "EMAIL_HOST", "mailhost")
        monkeypatch.setattr(configs, "EMAIL_PORT", 2525)
        monkeypatch.setattr(configs, "EMAIL_DOMAIN", "example.test")

        await send_email("a@example.com", "Hello subj", "<p>body</p>")

        assert len(smtp_calls) == 1
        message, kwargs = smtp_calls[0]
        assert kwargs == {"hostname": "mailhost", "port": 2525}
        assert message["To"] == "a@example.com"
        assert message["Subject"] == "Hello subj"
        assert message["From"].addresses[0].addr_spec == "no-reply@example.test"
        assert message["Date"]
        assert message["Message-ID"].endswith("@example.test>")
        assert message.get_content_type() == "text/html"
        assert message["Reply-To"] is None

    async def test_reply_to_sets_header(self, monkeypatch, smtp_calls):
        monkeypatch.setattr(configs, "EMAIL_ENABLED", True)

        await send_email(
            "a@example.com",
            "Hello subj",
            "<p>body</p>",
            reply_to='"Visitor, Jr." <visitor@example.org>',
        )

        message, _ = smtp_calls[0]
        reply_to = message["Reply-To"].addresses[0]
        assert reply_to.addr_spec == "visitor@example.org"
        assert reply_to.display_name == "Visitor, Jr."

    @pytest.mark.parametrize(
        "error",
        [aiosmtplib.SMTPException("boom"), ConnectionRefusedError("refused")],
    )
    async def test_send_failure_is_logged_and_swallowed(
        self, monkeypatch, caplog, error
    ):
        monkeypatch.setattr(configs, "EMAIL_ENABLED", True)

        async def failing_send(message, **kwargs):
            raise error

        monkeypatch.setattr(email_module.aiosmtplib, "send", failing_send)

        with caplog.at_level(logging.ERROR, logger=email_module.logger.name):
            await send_email("a@example.com", "Hello subj", "<p>body</p>")

        assert "Failed to send email to a@example.com" in caplog.text


class TestGetTemplate:
    def test_autoescapes_injected_values(self):
        output = get_template(
            "auth/templates/activation.html",
            activation_link="http://x/?a=1&b=<script>alert(1)</script>",
        )

        assert "<script>alert(1)</script>" not in output
        assert "&lt;script&gt;" in output

    def test_renders_link_in_href(self):
        output = get_template(
            "auth/templates/activation.html",
            activation_link="http://site/activate?token=abc-123",
        )

        assert 'href="http://site/activate?token=abc-123"' in output
