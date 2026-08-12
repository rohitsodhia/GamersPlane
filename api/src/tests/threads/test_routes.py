from app.models import Thread
from tests.factories import ForumFactory, PostFactory, ThreadFactory, prose_doc


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
        forum = await create(ForumFactory, heritage=[])
        await create_thread(create, db_session, forum=forum)

        response = await client.get("/threads", params={"forum_id": forum.id})

        assert response.status_code == 200

    async def test_get_threads_unknown_forum_returns_404(self, client):
        response = await client.get("/threads", params={"forum_id": 999999})

        assert response.status_code == 404

    async def test_get_threads_returns_threads_for_forum(
        self, client, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[])
        thread, _first_post = await create_thread(create, db_session, forum=forum)

        response = await client.get("/threads", params={"forum_id": forum.id})

        body = response.json()
        assert [t["id"] for t in body["threads"]] == [thread.id]

    async def test_get_threads_filters_by_forum_id(self, client, create, db_session):
        forum = await create(ForumFactory, heritage=[])
        other_forum = await create(ForumFactory, heritage=[])
        await create_thread(create, db_session, forum=forum)
        await create_thread(create, db_session, forum=other_forum)

        response = await client.get("/threads", params={"forum_id": forum.id})

        body = response.json()
        assert len(body["threads"]) == 1

    async def test_get_threads_empty_when_no_threads(self, client, create):
        forum = await create(ForumFactory, heritage=[])

        response = await client.get("/threads", params={"forum_id": forum.id})

        assert response.status_code == 200
        assert response.json()["threads"] == []

    async def test_get_threads_returns_count_and_page(self, client, create, db_session):
        forum = await create(ForumFactory, heritage=[])
        await create_thread(create, db_session, forum=forum)

        response = await client.get("/threads", params={"forum_id": forum.id})

        body = response.json()
        assert body["count"] == 1
        assert body["page"] == 1

    async def test_get_threads_second_page_empty_within_first_page_limit(
        self, client, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[])
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
        forum = await create(ForumFactory, heritage=[])
        thread, _first_post = await create_thread(create, db_session, forum=forum)

        response = await client.get(
            "/threads", params={"forum_id": forum.id, "page": 0}
        )

        body = response.json()
        assert body["page"] == 1
        assert [t["id"] for t in body["threads"]] == [thread.id]


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
        forum = await create(ForumFactory, heritage=[])

        response = await client.post(
            "/threads", json=new_thread_payload(forum_id=forum.id)
        )

        assert response.status_code == 403

    async def test_create_thread(self, authed_client, create):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[])

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
        forum = await create(ForumFactory, heritage=[])

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

    async def test_create_thread_sets_options(self, authed_client, create):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[])

        response = await client.post(
            "/threads",
            json=new_thread_payload(forum_id=forum.id, options={"sticky": True}),
        )
        thread_id = response.json()["id"]

        list_response = await client.get("/threads", params={"forum_id": forum.id})
        thread = next(
            t for t in list_response.json()["threads"] if t["id"] == thread_id
        )
        assert thread["options"] == Thread.Options(sticky=True).model_dump(
            mode="json"
        )

    async def test_create_thread_rejects_unknown_option(self, authed_client, create):
        client, _user = authed_client
        forum = await create(ForumFactory, heritage=[])

        response = await client.post(
            "/threads",
            json=new_thread_payload(
                forum_id=forum.id, options={"not_a_real_option": True}
            ),
        )

        assert response.status_code == 422
