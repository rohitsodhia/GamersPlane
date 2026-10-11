import pytest

from app.configs import configs
from app.contact import rate_limit

VALID = {
    "name": "Pat Visitor",
    "email": "pat@example.org",
    "subject": "Hello there",
    "message": "I have thoughts.",
}


def body(**overrides):
    return {**VALID, **overrides}


class TestSendContact:
    async def test_success_logged_out_with_username(self, client, sent):
        response = await client.post("/contact", json=body(username="patty"))

        assert response.status_code == 200
        assert response.json() == {"success": True}
        sent.assert_awaited_once()
        to, subject, content = sent.await_args.args
        assert to == configs.CONTACT_EMAIL
        assert subject == "Gamers' Plane Contact: Hello there"
        assert "Pat Visitor" in content
        assert "pat@example.org" in content
        assert "patty" in content
        assert "I have thoughts." in content

    async def test_reply_to_is_visitor(self, client, sent):
        await client.post("/contact", json=body(name="Pat, Jr."))

        reply_to = sent.await_args.kwargs["reply_to"]
        assert reply_to == '"Pat, Jr." <pat@example.org>'

    async def test_message_is_escaped_and_keeps_line_breaks(self, client, sent):
        await client.post(
            "/contact", json=body(message="line one\nline <b>two</b>\n\nline four")
        )

        content = sent.await_args.args[2]
        assert "<b>two</b>" not in content
        assert "&lt;b&gt;two&lt;/b&gt;" in content
        assert "line one<br>line &lt;b&gt;" in content

    async def test_fields_are_stripped(self, client, sent):
        response = await client.post(
            "/contact", json=body(subject="  padded  ", message="\n hi \n")
        )

        assert response.status_code == 200
        assert sent.await_args.args[1] == "Gamers' Plane Contact: padded"
        assert "<p>hi</p>" in sent.await_args.args[2]

    async def test_logged_in_user_included_and_submitted_username_ignored(
        self, authed_client, sent
    ):
        client, user = authed_client

        response = await client.post("/contact", json=body(username="impostor"))

        assert response.status_code == 200
        content = sent.await_args.args[2]
        assert user.username in content
        assert f"id {user.id}" in content
        assert "impostor" not in content

    @pytest.mark.parametrize("field", ["name", "email", "subject", "message"])
    @pytest.mark.parametrize("value", ["", "   "])
    async def test_blank_required_field_rejected(self, client, sent, field, value):
        response = await client.post("/contact", json=body(**{field: value}))

        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == field
        sent.assert_not_awaited()

    async def test_invalid_email_rejected(self, client, sent):
        response = await client.post("/contact", json=body(email="not-an-email"))

        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "email"
        sent.assert_not_awaited()

    @pytest.mark.parametrize("field", ["subject", "name", "username"])
    @pytest.mark.parametrize("newline", ["\n", "\r"])
    async def test_newline_in_single_line_field_rejected(
        self, client, sent, field, newline
    ):
        response = await client.post(
            "/contact", json=body(**{field: f"first{newline}Bcc: x@example.org"})
        )

        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == field
        sent.assert_not_awaited()

    @pytest.mark.parametrize(
        "overrides",
        [
            {"name": "n" * 51},
            {"username": "u" * 51},
            {"subject": "s" * 101},
            {"message": "m" * 5001},
            {"email": "a" * 90 + "@example.org"},
        ],
    )
    async def test_too_long_rejected(self, client, sent, overrides):
        response = await client.post("/contact", json=body(**overrides))

        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == next(iter(overrides))
        sent.assert_not_awaited()

    async def test_max_lengths_accepted(self, client, sent):
        response = await client.post(
            "/contact",
            json=body(
                name="n" * 50,
                username="u" * 50,
                subject="s" * 100,
                message="m" * 5000,
            ),
        )

        assert response.status_code == 200
        sent.assert_awaited_once()


class TestHoneypot:
    async def test_filled_honeypot_is_silently_dropped(self, client, sent):
        response = await client.post(
            "/contact", json=body(website="http://spam.example")
        )

        assert response.status_code == 200
        assert response.json() == {"success": True}
        sent.assert_not_awaited()

    async def test_honeypot_submissions_do_not_use_up_the_rate_limit(
        self, client, sent
    ):
        for _ in range(rate_limit.RATE_LIMIT_MAX + 1):
            await client.post("/contact", json=body(website="spam"))

        response = await client.post("/contact", json=body())

        assert response.status_code == 200


class TestRateLimit:
    async def test_blocked_after_limit(self, client, sent):
        for _ in range(rate_limit.RATE_LIMIT_MAX):
            assert (await client.post("/contact", json=body())).status_code == 200

        response = await client.post("/contact", json=body())

        assert response.status_code == 429
        assert response.json()["errors"][0]["code"] == "rate_limited"
        assert sent.await_count == rate_limit.RATE_LIMIT_MAX

    async def test_invalid_submissions_do_not_count(self, client, sent):
        for _ in range(rate_limit.RATE_LIMIT_MAX + 1):
            await client.post("/contact", json=body(subject=""))

        response = await client.post("/contact", json=body())

        assert response.status_code == 200

    async def test_limit_is_per_rightmost_forwarded_ip(self, client, sent):
        def post(forwarded):
            return client.post(
                "/contact", json=body(), headers={"X-Forwarded-For": forwarded}
            )

        for _ in range(rate_limit.RATE_LIMIT_MAX):
            await post("9.9.9.9, 1.1.1.1")

        # Same real client (rightmost), different spoofed left side: still blocked
        assert (await post("8.8.8.8, 1.1.1.1")).status_code == 429
        # A different real client is unaffected
        assert (await post("9.9.9.9, 2.2.2.2")).status_code == 200


class TestRateLimitHelpers:
    async def test_client_ip_falls_back_to_connection_host(self, client, sent):
        for _ in range(rate_limit.RATE_LIMIT_MAX):
            await client.post("/contact", json=body())

        assert (await client.post("/contact", json=body())).status_code == 429

    def test_window_expires(self, monkeypatch):
        now = 1000.0
        monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now)
        for _ in range(rate_limit.RATE_LIMIT_MAX):
            assert rate_limit.allow("1.2.3.4")
        assert not rate_limit.allow("1.2.3.4")

        now += rate_limit.RATE_LIMIT_WINDOW_SECONDS + 1

        assert rate_limit.allow("1.2.3.4")
