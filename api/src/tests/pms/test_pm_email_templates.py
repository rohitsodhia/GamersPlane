import pytest

from app.configs import configs
from app.pms import functions as pm_functions
from app.pms.functions import (
    PM_PREFERENCE_LABEL,
    build_pm_preview,
    send_pm_email,
)


@pytest.fixture
def sent(monkeypatch):
    calls = []

    async def fake_send_email(to, subject, content, **kwargs):
        calls.append({"to": to, "subject": subject, "content": content, **kwargs})

    monkeypatch.setattr(pm_functions, "send_email", fake_send_email)
    return calls


async def _send(sent, **overrides):
    values = {
        "pm_id": 7,
        "sender_username": "alice",
        "title": "Hello",
        "preview": "Hi there",
        **overrides,
    }
    await send_pm_email("bob@example.com", **values)
    return sent[-1]


def _para(*nodes):
    return {"type": "paragraph", "content": list(nodes)}


def _text(text):
    return {"type": "text", "text": text}


def _doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


class TestPMEmailTemplate:
    async def test_contents(self, sent):
        mail = await _send(sent)

        assert mail["to"] == "bob@example.com"
        assert mail["subject"] == "New message from alice"
        html = mail["content"]
        assert "New message" in html
        assert "alice sent you a private message:" in html
        assert "Hello" in html
        assert "Hi there" in html
        assert f'href="{configs.HOST_NAME}/pms/7"' in html
        assert f'href="{configs.HOST_NAME}/profile"' in html
        assert f'labeled "{PM_PREFERENCE_LABEL}"' in html

    async def test_user_input_escaped_once(self, sent):
        mail = await _send(
            sent,
            sender_username="<b>Al & Co</b>",
            title="<i>Rock & Roll</i>",
            preview="<script>alert(1)</script> Tom & Jerry",
        )

        html = mail["content"]
        assert "<script>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt; Tom &amp; Jerry" in html
        assert "&lt;i&gt;Rock &amp; Roll&lt;/i&gt;" in html
        assert "&lt;b&gt;Al &amp; Co&lt;/b&gt; sent you" in html
        assert "&amp;amp;" not in html

    async def test_empty_preview_omits_the_preview_block(self, sent):
        full = await _send(sent, preview="Hi there")
        empty = await _send(sent, preview="")

        assert "Hi there" in full["content"]
        assert full["content"].count("<p>") == empty["content"].count("<p>") + 1

    async def test_title_br_becomes_a_space(self, sent):
        mail = await _send(sent, title="Line one<br>Line two")

        assert "Line one Line two" in mail["content"]
        assert "&lt;br&gt;" not in mail["content"]


class TestBuildPMPreview:
    def test_image_becomes_placeholder(self):
        body = _doc(_para(_text("before")), {"type": "image", "attrs": {"src": "x"}})

        assert build_pm_preview(body) == "before [image]"
        assert build_pm_preview(_doc({"type": "image"})) == "[image]"

    def test_quote_is_excluded(self):
        body = _doc(
            _para(_text("reply")),
            {"type": "quote", "content": [_para(_text("quoted"))]},
        )

        assert build_pm_preview(body) == "reply"

    def test_quote_only_or_empty_message_has_no_preview(self):
        quote_only = _doc({"type": "quote", "content": [_para(_text("quoted"))]})

        assert build_pm_preview(quote_only) == ""
        assert build_pm_preview(_doc()) == ""

    def test_long_message_is_cut_at_300_with_an_ellipsis(self):
        preview = build_pm_preview(_doc(_para(_text("a" * 400))))

        assert preview == "a" * 299 + "…"
        assert len(preview) == 300
