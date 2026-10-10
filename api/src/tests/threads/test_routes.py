from datetime import UTC, datetime, timedelta

import pytest

from app.configs import configs
from app.models import Post, RolePermission, Thread
from app.repositories import ThreadRepository
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import (
    ForumFactory,
    PostFactory,
    RoleFactory,
    ThreadFactory,
    UserFactory,
    prose_doc,
)

Verbs = RolePermission.ValidPermissions


async def grant(db_session, user, forum, *verbs):
    """Give ``user`` a role holding ``verbs`` on ``forum``."""
    role = RoleFactory.build()
    db_session.add(role)
    for verb in verbs:
        role.grant(verb, scope_type=RolePermission.ScopeTypes.FORUM, scope_id=forum.id)
    role.users.append(user)
    await db_session.flush()


async def make_moderator(db_session, user, forum):
    await grant(db_session, user, forum, Verbs.FORUM_MODERATE)


async def closed_forum(create):
    """A forum outside the site root, so no default grants reach it."""
    return await create(ForumFactory, heritage=[])


WEBHOOK_URL = "https://discord.com/api/webhooks/123456789/abc-DEF_123"


async def create_thread(create, db_session, **thread_kwargs):
    thread = await create(ThreadFactory, **thread_kwargs)
    first_post = await create(PostFactory, thread=thread, title="First Post")
    thread.first_post_id = first_post.id
    thread.last_post_id = first_post.id
    thread.last_post_at = first_post.published_at
    thread.post_count = 1
    await db_session.flush()
    return thread, first_post


class TestGetThreads:
    async def test_get_threads_is_public(self, client, create, db_session):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await create_thread(create, db_session, forum=forum)

        response = await client.get("/threads", params={"forum_id": forum.id})

        assert response.status_code == 200

    async def test_get_threads_unknown_forum_returns_404(self, client):
        response = await client.get("/threads", params={"forum_id": 999999})

        assert response.status_code == 404

    async def test_get_threads_returns_threads_for_forum(
        self, client, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, _first_post = await create_thread(create, db_session, forum=forum)

        response = await client.get("/threads", params={"forum_id": forum.id})

        body = response.json()
        assert [t["id"] for t in body["threads"]] == [thread.id]

    async def test_get_threads_filters_by_forum_id(self, client, create, db_session):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        other_forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await create_thread(create, db_session, forum=forum)
        await create_thread(create, db_session, forum=other_forum)

        response = await client.get("/threads", params={"forum_id": forum.id})

        body = response.json()
        assert len(body["threads"]) == 1

    async def test_get_threads_empty_when_no_threads(self, client, create):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])

        response = await client.get("/threads", params={"forum_id": forum.id})

        assert response.status_code == 200
        assert response.json()["threads"] == []

    async def test_get_threads_returns_count_and_page(self, client, create, db_session):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await create_thread(create, db_session, forum=forum)

        response = await client.get("/threads", params={"forum_id": forum.id})

        body = response.json()
        assert body["count"] == 1
        assert body["page"] == 1

    async def test_get_threads_second_page_empty_within_first_page_limit(
        self, client, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await create_thread(create, db_session, forum=forum)

        response = await client.get(
            "/threads", params={"forum_id": forum.id, "page": 2}
        )

        body = response.json()
        assert body["threads"] == []
        assert body["page"] == 2
        assert body["count"] == 1

    async def test_get_threads_defaults_to_page_one_when_page_below_one(
        self, client, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, _first_post = await create_thread(create, db_session, forum=forum)

        response = await client.get(
            "/threads", params={"forum_id": forum.id, "page": 0}
        )

        body = response.json()
        assert body["page"] == 1
        assert [t["id"] for t in body["threads"]] == [thread.id]

    async def test_get_threads_never_returns_discord_webhook(
        self, client, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await create_thread(
            create,
            db_session,
            forum=forum,
            options=Thread.Options(discord_webhook=WEBHOOK_URL),
        )

        response = await client.get("/threads", params={"forum_id": forum.id})

        assert "discord_webhook" not in response.json()["threads"][0]["options"]

    async def test_get_threads_unreadable_forum_returns_404(self, client, create):
        forum = await closed_forum(create)

        response = await client.get("/threads", params={"forum_id": forum.id})

        assert response.status_code == 404


class TestGetThread:
    async def test_get_thread_is_public(self, client, create, db_session):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, _first_post = await create_thread(create, db_session, forum=forum)

        response = await client.get(f"/threads/{thread.id}")

        assert response.status_code == 200

    async def test_get_thread_not_found(self, client):
        response = await client.get("/threads/999999")

        assert response.status_code == 404

    async def test_get_thread_returns_fields(self, client, create, db_session):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, first_post = await create_thread(
            create,
            db_session,
            forum=forum,
            options=Thread.Options(locked=True),
        )

        response = await client.get(f"/threads/{thread.id}")

        body = response.json()
        assert body["id"] == thread.id
        assert body["forum_id"] == forum.id
        assert body["title"] == "First Post"
        assert body["first_post_id"] == first_post.id
        assert body["options"] == {
            "sticky": False,
            "locked": True,
            "allow_public_posting": False,
            "allow_rolls": False,
            "allow_draws": False,
        }

    async def test_get_thread_never_returns_discord_webhook(
        self, client, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, _first_post = await create_thread(
            create,
            db_session,
            forum=forum,
            options=Thread.Options(discord_webhook=WEBHOOK_URL),
        )

        response = await client.get(f"/threads/{thread.id}")

        assert "discord_webhook" not in response.json()["options"]

    async def test_get_thread_returns_principals_forum_permissions(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await closed_forum(create)
        await grant(db_session, user, forum, Verbs.FORUM_READ, Verbs.FORUM_WRITE)
        thread, _first_post = await create_thread(create, db_session, forum=forum)

        response = await client.get(f"/threads/{thread.id}")

        assert response.json()["permissions"] == ["forum_read", "forum_write"]

    async def test_get_thread_in_unreadable_forum_returns_404(
        self, client, create, db_session
    ):
        forum = await closed_forum(create)
        thread, _first_post = await create_thread(create, db_session, forum=forum)

        response = await client.get(f"/threads/{thread.id}")

        assert response.status_code == 404


def new_thread_payload(**overrides):
    payload = {
        "forum_id": None,
        "title": "Hello",
        "body": prose_doc("Hi there"),
        "options": {},
    }
    payload.update(overrides)
    return payload


class TestCreateThread:
    async def test_create_thread_requires_auth(self, client, create):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])

        response = await client.post(
            "/threads", json=new_thread_payload(forum_id=forum.id)
        )

        assert response.status_code == 403

    async def test_create_thread(self, authed_client, create):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])

        response = await client.post(
            "/threads", json=new_thread_payload(forum_id=forum.id)
        )

        assert response.status_code == 200
        assert "id" in response.json()

    async def test_create_thread_with_a_webhook_sends_the_first_post(
        self, authed_client, create, db_session, sent_webhooks
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_moderator(db_session, user, forum)
        webhook = "https://discord.com/api/webhooks/123456789/abc-DEF_123"

        response = await client.post(
            "/threads",
            json=new_thread_payload(
                forum_id=forum.id, options={"discord_webhook": webhook}
            ),
        )

        [(url, payload)] = sent_webhooks
        assert url == webhook
        assert payload["username"] == user.username
        embed = payload["embeds"][0]
        assert embed["title"] == "Hello"
        assert f"/forums/thread/{response.json()['id']}?page=1#post-" in embed["url"]
        assert embed["footer"]["text"] == user.username

    async def test_create_thread_without_a_webhook_sends_nothing(
        self, authed_client, create, sent_webhooks
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])

        await client.post("/threads", json=new_thread_payload(forum_id=forum.id))

        assert sent_webhooks == []

    async def test_create_thread_unknown_forum_returns_404(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/threads", json=new_thread_payload(forum_id=999999)
        )

        assert response.status_code == 404

    async def test_create_thread_creates_first_post(self, authed_client, create):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])

        response = await client.post(
            "/threads", json=new_thread_payload(forum_id=forum.id)
        )
        thread_id = response.json()["id"]

        list_response = await client.get("/threads", params={"forum_id": forum.id})
        thread = list_response.json()["threads"][0]
        assert thread["id"] == thread_id
        assert thread["first_post"]["title"] == "Hello"
        assert thread["post_count"] == 1
        assert thread["first_post"]["id"] == thread["last_post"]["id"]
        assert thread["first_post"]["author"]["id"] == user.id

    async def test_create_thread_sets_options(self, authed_client, create, db_session):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_moderator(db_session, user, forum)

        response = await client.post(
            "/threads",
            json=new_thread_payload(forum_id=forum.id, options={"sticky": True}),
        )
        thread_id = response.json()["id"]

        list_response = await client.get("/threads", params={"forum_id": forum.id})
        thread = next(
            t for t in list_response.json()["threads"] if t["id"] == thread_id
        )
        assert thread["options"]["sticky"] is True

    async def test_create_thread_without_create_permission_returns_403(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await closed_forum(create)
        await grant(db_session, user, forum, Verbs.FORUM_READ, Verbs.FORUM_WRITE)

        response = await client.post(
            "/threads", json=new_thread_payload(forum_id=forum.id)
        )

        assert response.status_code == 403

    async def test_create_thread_non_moderator_setting_sticky_returns_403(
        self, authed_client, create
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])

        response = await client.post(
            "/threads",
            json=new_thread_payload(forum_id=forum.id, options={"sticky": True}),
        )

        assert response.status_code == 403

    async def test_create_thread_empty_webhook_counts_as_unset(
        self, authed_client, create
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])

        response = await client.post(
            "/threads",
            json=new_thread_payload(forum_id=forum.id, options={"discord_webhook": ""}),
        )

        assert response.status_code == 200

    async def stored_webhook(self, client, db_session, forum, webhook):
        """Create a thread with ``webhook`` and return what was stored."""
        response = await client.post(
            "/threads",
            json=new_thread_payload(
                forum_id=forum.id, options={"discord_webhook": webhook}
            ),
        )
        assert response.status_code == 200
        thread = await db_session.get(Thread, response.json()["id"])
        await db_session.refresh(thread)
        return thread.options.discord_webhook

    @pytest.mark.parametrize(
        "webhook",
        [
            "https://discord.com/api/webhooks/123/abc-DEF_1",
            "https://discordapp.com/api/webhooks/123/abc",
            "https://ptb.discord.com/api/v10/webhooks/123/abc",
        ],
    )
    async def test_create_thread_stores_valid_discord_webhook(
        self, authed_client, create, db_session, webhook
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_moderator(db_session, user, forum)

        stored = await self.stored_webhook(client, db_session, forum, webhook)

        assert stored == webhook

    async def test_create_thread_strips_whitespace_around_discord_webhook(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_moderator(db_session, user, forum)

        stored = await self.stored_webhook(
            client, db_session, forum, f"  {WEBHOOK_URL}\n"
        )

        assert stored == WEBHOOK_URL

    async def test_create_thread_blank_discord_webhook_is_stored_as_none(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])

        stored = await self.stored_webhook(client, db_session, forum, "   ")

        assert stored is None

    @pytest.mark.parametrize(
        "webhook",
        [
            "http://discord.com/api/webhooks/123/abc",
            "https://example.com/api/webhooks/123/abc",
            "https://discord.com.evil.test/api/webhooks/123/abc",
            "https://discord.com/api/webhooks/123/abc/extra",
            "https://discord.com/api/webhooks/abc/def",
        ],
    )
    async def test_create_thread_invalid_discord_webhook_returns_422(
        self, authed_client, create, db_session, webhook
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_moderator(db_session, user, forum)

        response = await client.post(
            "/threads",
            json=new_thread_payload(
                forum_id=forum.id, options={"discord_webhook": webhook}
            ),
        )

        assert response.status_code == 422
        error = response.json()["errors"][0]
        assert error["field"] == "options.discord_webhook"
        assert error["detail"].startswith("Discord webhook must be a Discord webhook")

    async def test_create_thread_allow_rolls_needs_add_rolls_not_moderate(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        payload = new_thread_payload(forum_id=forum.id, options={"allow_rolls": True})

        denied = await client.post("/threads", json=payload)
        await grant(db_session, user, forum, Verbs.FORUM_ADD_ROLLS)
        allowed = await client.post("/threads", json=payload)

        assert denied.status_code == 403
        assert allowed.status_code == 200

    async def test_create_thread_rejects_unknown_option(self, authed_client, create):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])

        response = await client.post(
            "/threads",
            json=new_thread_payload(
                forum_id=forum.id, options={"not_a_real_option": True}
            ),
        )

        assert response.status_code == 422

    async def test_create_thread_is_read_for_its_author(self, authed_client, create):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])

        await client.post("/threads", json=new_thread_payload(forum_id=forum.id))

        listing = await client.get("/threads", params={"forum_id": forum.id})
        assert listing.json()["threads"][0]["has_unread"] is False


async def owned_thread(create, db_session, author, forum, **options):
    """A thread whose first post is by ``author``, with the given options set."""
    thread = await create(ThreadFactory, forum=forum, options=Thread.Options(**options))
    first_post = await create(PostFactory, thread=thread, author=author)
    # The relationship, not just the id: it was already loaded (as None).
    thread.first_post = first_post
    await db_session.flush()
    return thread


class TestUpdateThread:
    async def test_moderator_can_lock_and_sticky(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_moderator(db_session, user, forum)
        author = await create(UserFactory)
        thread = await owned_thread(create, db_session, author, forum)

        response = await client.patch(
            f"/threads/{thread.id}", json={"options": {"locked": True, "sticky": True}}
        )

        assert response.status_code == 200
        assert response.json()["locked"] is True
        assert response.json()["sticky"] is True
        await db_session.refresh(thread)
        assert thread.options.locked is True
        assert thread.options.sticky is True

    async def test_response_has_public_options_only(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread = await owned_thread(
            create, db_session, user, forum, discord_webhook=WEBHOOK_URL
        )

        response = await client.patch(f"/threads/{thread.id}", json={"options": {}})

        assert response.status_code == 200
        assert "discord_webhook" not in response.json()

    async def test_author_cannot_lock_without_moderate(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread = await owned_thread(create, db_session, user, forum)

        response = await client.patch(
            f"/threads/{thread.id}", json={"options": {"locked": True}}
        )

        assert response.status_code == 403
        await db_session.refresh(thread)
        assert thread.options.locked is False

    async def test_author_can_toggle_allow_rolls_with_add_rolls(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread = await owned_thread(create, db_session, user, forum)
        path = f"/threads/{thread.id}"
        body = {"options": {"allow_rolls": True}}

        denied = await client.patch(path, json=body)
        await grant(db_session, user, forum, Verbs.FORUM_ADD_ROLLS)
        allowed = await client.patch(path, json=body)

        assert denied.status_code == 403
        assert allowed.status_code == 200
        assert allowed.json()["allow_rolls"] is True

    async def test_turning_an_option_off_needs_its_verb_too(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread = await owned_thread(create, db_session, user, forum, allow_rolls=True)

        response = await client.patch(
            f"/threads/{thread.id}", json={"options": {"allow_rolls": False}}
        )

        assert response.status_code == 403
        await db_session.refresh(thread)
        assert thread.options.allow_rolls is True

    async def test_non_author_non_moderator_gets_403(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        author = await create(UserFactory)
        thread = await owned_thread(create, db_session, author, forum)

        response = await client.patch(f"/threads/{thread.id}", json={"options": {}})

        assert response.status_code == 403

    async def test_author_cannot_change_a_locked_thread(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await grant(db_session, user, forum, Verbs.FORUM_ADD_ROLLS)
        thread = await owned_thread(create, db_session, user, forum, locked=True)

        response = await client.patch(
            f"/threads/{thread.id}", json={"options": {"allow_rolls": True}}
        )

        assert response.status_code == 403

    async def test_moderator_can_unlock_a_locked_thread(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_moderator(db_session, user, forum)
        author = await create(UserFactory)
        thread = await owned_thread(create, db_session, author, forum, locked=True)

        response = await client.patch(
            f"/threads/{thread.id}", json={"options": {"locked": False}}
        )

        assert response.status_code == 200
        assert response.json()["locked"] is False

    async def test_unreadable_thread_returns_404(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await closed_forum(create)
        thread = await owned_thread(create, db_session, user, forum)

        response = await client.patch(
            f"/threads/{thread.id}", json={"options": {"allow_rolls": True}}
        )

        assert response.status_code == 404

    async def test_unknown_thread_returns_404(self, authed_client):
        client, _user = authed_client

        response = await client.patch("/threads/999999", json={"options": {}})

        assert response.status_code == 404

    async def test_sent_but_unchanged_moderator_option_is_allowed(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread = await owned_thread(create, db_session, user, forum, sticky=True)

        response = await client.patch(
            f"/threads/{thread.id}", json={"options": {"sticky": True}}
        )

        assert response.status_code == 200
        assert response.json()["sticky"] is True

    async def test_null_boolean_is_treated_as_not_sent(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread = await owned_thread(create, db_session, user, forum, sticky=True)

        response = await client.patch(
            f"/threads/{thread.id}", json={"options": {"sticky": None}}
        )

        assert response.status_code == 200
        assert response.json()["sticky"] is True

    async def test_partial_update_leaves_unsent_options_intact(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_moderator(db_session, user, forum)
        thread = await owned_thread(
            create, db_session, user, forum, sticky=True, discord_webhook=WEBHOOK_URL
        )

        response = await client.patch(
            f"/threads/{thread.id}", json={"options": {"locked": True}}
        )

        assert response.status_code == 200
        await db_session.refresh(thread)
        assert thread.options.locked is True
        assert thread.options.sticky is True
        assert thread.options.discord_webhook == WEBHOOK_URL

    @pytest.mark.parametrize("cleared", ["", None])
    async def test_webhook_can_be_cleared(
        self, authed_client, create, db_session, cleared
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_moderator(db_session, user, forum)
        thread = await owned_thread(
            create, db_session, user, forum, discord_webhook=WEBHOOK_URL
        )

        response = await client.patch(
            f"/threads/{thread.id}", json={"options": {"discord_webhook": cleared}}
        )

        assert response.status_code == 200
        await db_session.refresh(thread)
        assert thread.options.discord_webhook is None

    async def test_webhook_is_stripped_and_stored(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_moderator(db_session, user, forum)
        thread = await owned_thread(create, db_session, user, forum)

        response = await client.patch(
            f"/threads/{thread.id}",
            json={"options": {"discord_webhook": f"  {WEBHOOK_URL}\n"}},
        )

        assert response.status_code == 200
        await db_session.refresh(thread)
        assert thread.options.discord_webhook == WEBHOOK_URL

    async def test_invalid_webhook_returns_422(self, authed_client, create, db_session):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_moderator(db_session, user, forum)
        thread = await owned_thread(create, db_session, user, forum)

        response = await client.patch(
            f"/threads/{thread.id}",
            json={"options": {"discord_webhook": "https://example.com/hook"}},
        )

        assert response.status_code == 422
        error = response.json()["errors"][0]
        assert error["field"] == "options.discord_webhook"


BASE = datetime(2026, 1, 1, tzinfo=UTC)


async def add_post(create, db_session, thread, day):
    """Publish a post on ``thread`` ``day`` days after BASE."""
    post = await create(
        PostFactory, thread=thread, published_at=BASE + timedelta(days=day)
    )
    await ThreadRepository(db_session, principal=None).attach_new_post(thread, post)
    return post


async def make_thread(create, db_session, forum, *days):
    thread = await create(ThreadFactory, forum=forum)
    posts = [await add_post(create, db_session, thread, day) for day in days]
    return thread, posts


class TestThreadsUnreadFlag:
    async def test_get_threads_flags_only_unread_threads(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        unread, _ = await make_thread(create, db_session, forum, 1)
        read, _ = await make_thread(create, db_session, forum, 1)
        await client.post(f"/threads/{read.id}/mark-read")

        response = await client.get("/threads", params={"forum_id": forum.id})

        flags = {t["id"]: t["has_unread"] for t in response.json()["threads"]}
        assert flags == {unread.id: True, read.id: False}

    async def test_get_threads_has_unread_is_false_for_guests(
        self, client, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        await make_thread(create, db_session, forum, 1)

        response = await client.get("/threads", params={"forum_id": forum.id})

        assert response.json()["threads"][0]["has_unread"] is False


class TestGetThreadFirstUnread:
    async def test_unvisited_thread_points_at_first_post(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, posts = await make_thread(create, db_session, forum, 1, 2)

        body = (await client.get(f"/threads/{thread.id}")).json()

        assert body["first_unread_post_id"] == posts[0].id
        assert body["first_unread_page"] == 1

    async def test_first_unread_page_follows_pagination(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        per_page = configs.PAGINATE_PER_PAGE
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, posts = await make_thread(
            create, db_session, forum, *range(1, per_page + 2)
        )
        await client.post(
            f"/threads/{thread.id}/read", json={"post_id": posts[per_page - 1].id}
        )

        body = (await client.get(f"/threads/{thread.id}")).json()

        assert body["first_unread_post_id"] == posts[per_page].id
        assert body["first_unread_page"] == 2

    async def test_fully_read_thread_has_no_first_unread(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, _posts = await make_thread(create, db_session, forum, 1, 2)
        response = await client.post(f"/threads/{thread.id}/mark-read")

        assert response.status_code == 204
        body = (await client.get(f"/threads/{thread.id}")).json()
        assert body["first_unread_post_id"] is None
        assert body["first_unread_page"] is None

    async def test_guest_has_no_first_unread(self, client, create, db_session):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, _posts = await make_thread(create, db_session, forum, 1)

        body = (await client.get(f"/threads/{thread.id}")).json()

        assert body["first_unread_post_id"] is None
        assert body["first_unread_page"] is None


class TestMarkThreadViewed:
    async def test_requires_auth(self, client, create, db_session):
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, posts = await make_thread(create, db_session, forum, 1)

        response = await client.post(
            f"/threads/{thread.id}/read", json={"post_id": posts[0].id}
        )

        assert response.status_code == 403

    async def test_marks_thread_read_up_to_the_post(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, posts = await make_thread(create, db_session, forum, 1, 2)

        response = await client.post(
            f"/threads/{thread.id}/read", json={"post_id": posts[0].id}
        )

        assert response.status_code == 204
        body = (await client.get(f"/threads/{thread.id}")).json()
        assert body["first_unread_post_id"] == posts[1].id

    async def test_unreadable_forum_returns_404(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await closed_forum(create)
        thread, posts = await make_thread(create, db_session, forum, 1)

        response = await client.post(
            f"/threads/{thread.id}/read", json={"post_id": posts[0].id}
        )

        assert response.status_code == 404

    async def test_post_from_another_thread_returns_404(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, _posts = await make_thread(create, db_session, forum, 1)
        _other, other_posts = await make_thread(create, db_session, forum, 1)

        response = await client.post(
            f"/threads/{thread.id}/read", json={"post_id": other_posts[0].id}
        )

        assert response.status_code == 404

    async def test_nonexistent_post_returns_404(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, _posts = await make_thread(create, db_session, forum, 1)

        response = await client.post(
            f"/threads/{thread.id}/read", json={"post_id": 999999}
        )

        assert response.status_code == 404

    async def test_draft_post_returns_404(self, authed_client, create, db_session):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, _posts = await make_thread(create, db_session, forum, 1)
        draft = await create(PostFactory, thread=thread, state=Post.States.DRAFT)

        response = await client.post(
            f"/threads/{thread.id}/read", json={"post_id": draft.id}
        )

        assert response.status_code == 404


class TestMarkThreadReadAndUnread:
    async def test_mark_unread_makes_newest_post_unread(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
        thread, posts = await make_thread(create, db_session, forum, 1, 2)
        await client.post(f"/threads/{thread.id}/mark-read")

        response = await client.post(f"/threads/{thread.id}/mark-unread")

        assert response.status_code == 204
        body = (await client.get(f"/threads/{thread.id}")).json()
        assert body["first_unread_post_id"] == posts[1].id

    @pytest.mark.parametrize("action", ["mark-read", "mark-unread"])
    async def test_unreadable_forum_returns_404(
        self, authed_client, create, db_session, action
    ):
        client, _user = authed_client
        forum = await closed_forum(create)
        thread, _posts = await make_thread(create, db_session, forum, 1)

        response = await client.post(f"/threads/{thread.id}/{action}")

        assert response.status_code == 404

    async def test_mark_read_unknown_thread_returns_404(self, authed_client):
        client, _user = authed_client

        response = await client.post("/threads/999999/mark-read")

        assert response.status_code == 404
