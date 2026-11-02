import pytest

from app.configs import configs
from app.games import functions as game_functions
from app.games.functions import (
    GM_PREFERENCE_LABEL,
    PLAYER_PREFERENCE_LABEL,
    send_game_activity_email,
    send_new_game_email,
)
from app.helpers.email import get_template

# Titles are stored with newlines as <br> and are otherwise raw (no HTML escaping).
STORED_TITLE = "Rock & Roll<br>Part 2"


@pytest.fixture
def sent(monkeypatch):
    calls = []

    async def fake_send_email(to, subject, content, **kwargs):
        calls.append({"to": to, "subject": subject, "content": content, **kwargs})

    monkeypatch.setattr(game_functions, "send_email", fake_send_email)
    return calls


def _render(**overrides) -> str:
    values = {
        "game_id": 42,
        "title": "My Game",
        "system_name": "Pathfinder",
        "headline": "Something happened",
        "message": "Plain message",
        "preference_label": GM_PREFERENCE_LABEL,
    }
    return get_template("games/templates/game_activity.html", **{**values, **overrides})


class TestGameActivityTemplate:
    def test_contains_content_and_links(self):
        html = _render()

        assert "Something happened" in html
        assert "Pathfinder" in html
        assert "Plain message" in html
        assert f'href="{configs.HOST_NAME}/games/42"' in html
        assert f'href="{configs.HOST_NAME}/profile"' in html

        for label in (GM_PREFERENCE_LABEL, PLAYER_PREFERENCE_LABEL):
            assert f'labeled "{label}"' in _render(preference_label=label)

    def test_message_escaped_once(self):
        # Character names are stored raw, so the message embeds them as-is.
        html = _render(message='<script>alert(1)</script> "Tom & <Jerry>"')

        assert "<script>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "Tom &amp; &lt;Jerry&gt;" in html
        assert "&amp;amp;" not in html


class TestGameActivityIntro:
    def test_member_is_the_default_opening(self):
        assert "activity in your Pathfinder game" in _render()

    def test_former_opening_for_non_members(self):
        html = _render(intro="former")

        assert "an update about the Pathfinder game" in html
        assert "activity in your" not in html
        assert f'href="{configs.HOST_NAME}/games/42"' in html


def _render_invite(**overrides) -> str:
    values = {
        "game_id": 42,
        "title": "My Game",
        "system_id": "dnd5e",
        "system_name": "Pathfinder",
        "headline": "You're invited!",
        "inviter_username": "GM Bob",
        "preference_label": PLAYER_PREFERENCE_LABEL,
    }
    return get_template("games/templates/game_invite.html", **{**values, **overrides})


class TestGameInviteTemplate:
    def test_contains_content_and_links(self):
        html = _render_invite()

        assert "You&#39;re invited!" in html
        assert "GM Bob has invited you to their Pathfinder game" in html
        assert "activity in your" not in html
        assert f'href="{configs.HOST_NAME}/games/42"' in html
        assert f'labeled "{PLAYER_PREFERENCE_LABEL}"' in html

    @pytest.mark.parametrize(
        "system_id, has_logo", [("dnd5e", True), ("custom", False)]
    )
    def test_logo_skipped_for_custom(self, system_id, has_logo):
        html = _render_invite(system_id=system_id)

        assert (f"/images/logos/{system_id}.png" in html) is has_logo

    def test_user_input_escaped_once(self):
        html = _render_invite(title="<b>Rock & Roll</b>", inviter_username="A&<B>")

        assert "<b>Rock" not in html
        assert "&lt;b&gt;Rock &amp; Roll&lt;/b&gt;" in html
        assert "A&amp;&lt;B&gt;" in html
        assert "&amp;amp;" not in html


class TestEmailTitles:
    async def test_activity_email_title(self, sent):
        await send_game_activity_email(
            ["a@example.com"],
            game_id=1,
            title=STORED_TITLE,
            system_id="pathfinder",
            system_name="Pathfinder",
            subject="Hello",
            headline="Headline",
            message="Msg",
            preference_label=GM_PREFERENCE_LABEL,
        )

        assert sent[0]["subject"] == "[Rock & Roll Part 2] Hello"
        assert "Rock &amp; Roll Part 2" in sent[0]["content"]
        assert "&amp;amp;" not in sent[0]["content"]

    async def test_new_game_email_title(self, sent):
        await send_new_game_email(
            ["a@example.com"],
            game_id=1,
            title=STORED_TITLE,
            num_players=4,
            system_id="dnd5e",
            system_name="D&D 5e",
            gm_id=2,
            gm_username="gm",
        )

        assert sent[0]["subject"] == "New D&D 5e Game: Rock & Roll Part 2"
        assert "Rock &amp; Roll Part 2" in sent[0]["content"]
        assert "&amp;amp;" not in sent[0]["content"]

    @pytest.mark.parametrize(
        "system_id, has_logo", [("dnd5e", True), ("custom", False)]
    )
    async def test_new_game_email_logo_skipped_for_custom(
        self, sent, system_id, has_logo
    ):
        await send_new_game_email(
            ["a@example.com"],
            game_id=1,
            title="Game",
            num_players=4,
            system_id=system_id,
            system_name="Sys",
            gm_id=2,
            gm_username="gm",
        )

        assert (f"/images/logos/{system_id}.png" in sent[0]["content"]) is has_logo
