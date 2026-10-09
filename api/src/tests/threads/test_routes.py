from app.models import RolePermission, Thread
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import (
    ForumFactory,
    PostFactory,
    RoleFactory,
    ThreadFactory,
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


async def create_thread(create, db_session, **thread_kwargs):
    thread = await create(ThreadFactory, **thread_kwargs)
    first_post = await create(PostFactory, thread=thread, title="First Post")
    thread.first_post_id = first_post.id
    thread.last_post_id = first_post.id
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
        assert body["options"] == Thread.Options(locked=True).model_dump(mode="json")

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
        assert thread["options"] == Thread.Options(sticky=True).model_dump(mode="json")

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
