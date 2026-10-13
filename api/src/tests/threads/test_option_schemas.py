import pytest

from app.threads.option_schemas import clean_discord_webhook

VALID_WEBHOOKS = [
    "https://discord.com/api/webhooks/123/abc-DEF_1",
    "https://discordapp.com/api/webhooks/123/abc",
    "https://ptb.discord.com/api/v10/webhooks/123/abc",
    "https://canary.discord.com/api/webhooks/123/abc",
]

INVALID_WEBHOOKS = [
    "http://discord.com/api/webhooks/123/abc",
    "https://example.com/api/webhooks/123/abc",
    "https://discord.com.evil.test/api/webhooks/123/abc",
    "https://discord.com/api/webhooks/123/abc/extra",
    "https://discord.com/api/webhooks/abc/def",
]


class TestCleanDiscordWebhook:
    @pytest.mark.parametrize("webhook", VALID_WEBHOOKS)
    def test_valid_urls_pass_through(self, webhook):
        assert clean_discord_webhook(webhook) == webhook

    def test_surrounding_whitespace_is_stripped(self):
        webhook = VALID_WEBHOOKS[0]

        assert clean_discord_webhook(f"  {webhook}\n") == webhook

    @pytest.mark.parametrize("blank", [None, "", "   "])
    def test_blank_counts_as_unset(self, blank):
        assert clean_discord_webhook(blank) is None

    @pytest.mark.parametrize("webhook", INVALID_WEBHOOKS)
    def test_non_discord_urls_are_rejected(self, webhook):
        with pytest.raises(ValueError, match="Discord webhook"):
            clean_discord_webhook(webhook)
