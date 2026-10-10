from datetime import UTC, datetime

import httpx
import pytest

from app.configs import configs
from app.models import Character, CharacterAvatar
from app.threads import discord
from tests.factories import PostFactory, UserFactory, prose_doc

WEBHOOK_URL = "https://discord.com/api/webhooks/123456789/abc-DEF_123"


def build_payload(title="Hello", body=None, *, edited=False, username="alice"):
    author = UserFactory.build(username=username)
    post = PostFactory.build(
        id=77, title=title, body=body or prose_doc("Hi there"), author=author
    )
    return discord.build_post_payload(post, author, 5, 3, edited=edited)


def build_payload_as(character, *, username="alice"):
    author = UserFactory.build(username=username)
    post = PostFactory.build(
        id=77, body=prose_doc("Hi there"), author=author, posted_as=character
    )
    return discord.build_post_payload(post, author, 5, 3)


def build_character(**fields):
    fields.setdefault("name", "Aria")
    avatars = fields.pop("avatars", [CharacterAvatar(id=9, ext="png", is_primary=True)])
    return Character(id=4, avatars=avatars, **fields)


class TestBuildPostPayloadAsCharacter:
    def test_character_name_and_avatar_replace_the_authors(self):
        payload = build_payload_as(build_character())

        assert payload["username"] == "Aria"
        assert payload["avatar_url"] == f"{configs.AVATARS_ROOT}/characters/9.png"
        assert payload["embeds"][0]["footer"]["text"] == "alice"

    def test_character_without_an_avatar_does_not_borrow_the_authors(self):
        payload = build_payload_as(build_character(avatars=[]))

        assert payload["username"] == "Aria"
        assert "avatar_url" not in payload

    def test_non_http_character_avatar_is_omitted(self, monkeypatch):
        monkeypatch.setattr(configs, "AVATARS_ROOT", "/avatars")

        assert "avatar_url" not in build_payload_as(build_character())

    @pytest.mark.parametrize(
        "fields", [{"name": "  "}, {"name": None}, {"deleted": datetime.now(UTC)}]
    )
    def test_blank_or_deleted_character_falls_back_to_the_author(self, fields):
        payload = build_payload_as(build_character(**fields))

        assert payload["username"] == "alice"
        assert payload["avatar_url"].endswith("/avatars/users/avatar.png")


class TestBuildPostPayload:
    def test_embed_links_to_the_post_on_its_page(self):
        embed = build_payload()["embeds"][0]

        assert embed["url"] == f"{configs.HOST_NAME}/forums/thread/5?page=3#post-77"
        assert embed["title"] == "Hello"
        assert embed["description"] == "Hi there"
        assert embed["color"] == 13395456

    def test_username_and_avatar_come_from_the_author(self):
        payload = build_payload(username="alice")

        assert payload["username"] == "alice"
        assert payload["avatar_url"].endswith("/avatars/users/avatar.png")

    def test_avatar_is_omitted_when_it_is_not_an_absolute_url(self, monkeypatch):
        monkeypatch.setattr(configs, "AVATARS_ROOT", "/avatars")

        assert "avatar_url" not in build_payload()

    def test_leading_re_is_stripped_from_the_title(self):
        embed = build_payload(title="Re: Hello")["embeds"][0]

        assert embed["title"] == "Hello"

    def test_re_in_the_middle_of_a_title_is_kept(self):
        embed = build_payload(title="Hello Re: there")["embeds"][0]

        assert embed["title"] == "Hello Re: there"

    def test_footer_is_the_username(self):
        assert build_payload()["embeds"][0]["footer"]["text"] == "alice"

    def test_edited_footer_says_so(self):
        footer = build_payload(edited=True)["embeds"][0]["footer"]

        assert footer["text"] == "alice ~ edited post"

    def test_long_body_is_truncated_to_200_characters(self):
        description = build_payload(body=prose_doc("word " * 100))["embeds"][0][
            "description"
        ]

        assert len(description) == 200
        assert description.endswith("…")


class FailingTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request):
        raise httpx.ConnectError("boom")


@pytest.fixture(autouse=True)
def _enabled_logger(monkeypatch):
    # The migration run's alembic logging config disables already-created loggers.
    monkeypatch.setattr(discord.logger, "disabled", False)


def use_transport(monkeypatch, transport):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        discord.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )


class TestSendWebhook:
    async def test_posts_the_payload_as_json(self, monkeypatch):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(204)

        use_transport(monkeypatch, httpx.MockTransport(handler))

        await discord.send_webhook(WEBHOOK_URL, {"username": "alice"})

        assert [str(r.url) for r in requests] == [WEBHOOK_URL]
        assert requests[0].read() == b'{"username":"alice"}'

    async def test_never_posts_to_a_url_that_is_not_a_discord_webhook(
        self, monkeypatch
    ):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(204)

        use_transport(monkeypatch, httpx.MockTransport(handler))

        for url in (
            "https://discord.com/channels/1/2",
            "https://relay.example.com/api/webhooks/1/abc",
            "https://discord.com/api/webhooks/1/abc/extra",
            "http://discord.com/api/webhooks/1/abc",
        ):
            await discord.send_webhook(url, {})

        assert requests == []

    async def test_error_status_is_logged_not_raised(self, monkeypatch, caplog):
        use_transport(monkeypatch, httpx.MockTransport(lambda r: httpx.Response(500)))

        await discord.send_webhook(WEBHOOK_URL, {})

        assert "returned 500" in caplog.text

    async def test_network_failure_is_logged_not_raised(self, monkeypatch, caplog):
        use_transport(monkeypatch, FailingTransport())

        await discord.send_webhook(WEBHOOK_URL, {})

        assert "Discord webhook failed" in caplog.text
