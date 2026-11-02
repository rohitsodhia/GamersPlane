import pytest

from app.configs import configs
from app.forum_subscriptions.functions import Trigger, send_subscription_email

# Titles are stored with newlines as <br> and are otherwise raw (no HTML escaping).
THREAD_TITLE = "Rock & Roll<br>Part 2"


async def render(sent, **overrides):
    values = {
        "mode": "all",
        "kind": "thread",
        "trigger": Trigger.NEW_POST,
        "actor_username": "Alice",
        "thread_id": 7,
        "thread_title": "Dragon Hunt",
        "forum_id": 3,
        "forum_title": "Tavern",
        "post_id": 99,
    }
    await send_subscription_email(["a@example.com"], **{**values, **overrides})
    return sent[-1]


class TestAllVariant:
    async def test_new_post_names_who_thread_and_forum(self, sent):
        email = await render(sent)

        assert (
            'Alice made a new post in the thread "<a href="'
            f'{configs.HOST_NAME}/forums/thread/7?p=99#p99">Dragon Hunt</a>" in the '
            f'<a href="{configs.HOST_NAME}/forums/3">Tavern</a> forum.'
        ) in email["content"]
        assert email["subject"] == 'New post in "Dragon Hunt"'

    async def test_new_thread_wording(self, sent):
        email = await render(sent, trigger=Trigger.NEW_THREAD)

        assert (
            f'Alice started a new thread "<a href="{configs.HOST_NAME}/forums/thread/7">'
            "Dragon Hunt</a>"
        ) in email["content"]
        assert email["subject"] == "New thread in Tavern: Dragon Hunt"

    async def test_edit_wording(self, sent):
        email = await render(sent, trigger=Trigger.EDIT)

        assert "Alice edited a post in the thread" in email["content"]
        assert email["subject"] == 'Post edited in "Dragon Hunt"'


class TestNewContentVariant:
    async def test_thread_wording_has_no_poster_name(self, sent):
        email = await render(sent, mode="new content", kind="thread")

        assert "There's new activity in your subscribed thread: " in email["content"]
        assert (
            f'href="{configs.HOST_NAME}/forums/thread/7">Dragon Hunt</a>'
            in (email["content"])
        )
        assert "Alice" not in email["content"]

    async def test_forum_wording_has_no_poster_name(self, sent):
        email = await render(sent, mode="new content", kind="forum")

        assert "There's new activity in your subscribed forum: " in email["content"]
        assert f'href="{configs.HOST_NAME}/forums/3">Tavern</a>' in email["content"]
        assert "Alice" not in email["content"]
        assert "New thread:" not in email["content"]

    async def test_forum_wording_for_a_new_thread_links_the_thread(self, sent):
        email = await render(
            sent, mode="new content", kind="forum", trigger=Trigger.NEW_THREAD
        )

        assert "New thread: " in email["content"]
        assert (
            f'href="{configs.HOST_NAME}/forums/thread/7">Dragon Hunt</a>'
            in (email["content"])
        )

    async def test_subjects_differ_by_subscription_kind(self, sent):
        thread_email = await render(sent, mode="new content", kind="thread")
        forum_email = await render(sent, mode="new content", kind="forum")

        assert thread_email["subject"] == 'New activity in the thread "Dragon Hunt"'
        assert forum_email["subject"] == "New activity in the Tavern forum"


class TestCommon:
    @pytest.mark.parametrize(
        "kind, wording",
        [("thread", "subscribed to this thread"), ("forum", "this forum")],
    )
    async def test_footer_links_to_manage_subscriptions(self, sent, kind, wording):
        email = await render(sent, kind=kind)

        assert f'href="{configs.HOST_NAME}/forums/subscriptions"' in email["content"]
        assert wording in email["content"]

    async def test_titles_are_escaped_once_and_newlines_flattened(self, sent):
        email = await render(sent, thread_title=THREAD_TITLE, forum_title="<b>Hi</b>")

        assert "Rock &amp; Roll Part 2" in email["content"]
        assert "&lt;b&gt;Hi&lt;/b&gt;" in email["content"]
        assert "&amp;amp;" not in email["content"]
        assert email["subject"] == 'New post in "Rock & Roll Part 2"'

    async def test_sent_as_a_bcc_mass_mail(self, sent):
        email = await render(sent)

        assert email["to"] == configs.CONTACT_EMAIL
        assert email["bcc"] == ["a@example.com"]
        assert email["mass"] is True
