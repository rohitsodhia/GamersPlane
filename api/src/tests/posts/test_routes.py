from app.configs import configs
from app.models import Thread
from tests.factories import PostFactory, ThreadFactory, UserFactory, prose_doc


class TestGetPosts:
    async def test_get_posts_is_public(self, client, create):
        thread = await create(ThreadFactory)
        await create(PostFactory, thread=thread)

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert response.status_code == 200

    async def test_get_posts_unknown_thread_returns_404(self, client):
        response = await client.get("/posts", params={"thread_id": 999999})

        assert response.status_code == 404

    async def test_get_posts_returns_posts_for_thread(self, client, create):
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread, title="Hello")

        response = await client.get("/posts", params={"thread_id": thread.id})

        body = response.json()
        assert [p["id"] for p in body["posts"]] == [post.id]
        assert body["posts"][0]["title"] == "Hello"

    async def test_get_posts_filters_by_thread_id(self, client, create):
        thread = await create(ThreadFactory)
        other_thread = await create(ThreadFactory)
        await create(PostFactory, thread=thread)
        await create(PostFactory, thread=other_thread)

        response = await client.get("/posts", params={"thread_id": thread.id})

        body = response.json()
        assert len(body["posts"]) == 1

    async def test_get_posts_empty_when_no_posts(self, client, create):
        thread = await create(ThreadFactory)

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert response.status_code == 200
        assert response.json()["posts"] == []

    async def test_get_posts_second_page_empty_within_first_page_limit(
        self, client, create
    ):
        thread = await create(ThreadFactory)
        await create(PostFactory, thread=thread)

        response = await client.get(
            "/posts", params={"thread_id": thread.id, "page": 2}
        )

        body = response.json()
        assert body["posts"] == []
        assert body["page"] == 2
        assert body["count"] == 1

    async def test_get_posts_defaults_to_page_one_when_page_below_one(
        self, client, create
    ):
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread)

        response = await client.get(
            "/posts", params={"thread_id": thread.id, "page": 0}
        )

        body = response.json()
        assert body["page"] == 1
        assert [p["id"] for p in body["posts"]] == [post.id]

    async def test_get_posts_returns_author_with_avatar_url(self, client, create):
        user = await create(UserFactory, username="Alice")
        thread = await create(ThreadFactory)
        await create(PostFactory, thread=thread, author=user)

        response = await client.get("/posts", params={"thread_id": thread.id})

        author = response.json()["posts"][0]["author"]
        assert author["id"] == user.id
        assert author["username"] == "Alice"
        assert author["avatar"] == f"{configs.AVATARS_ROOT}/avatar.png"


def new_post_payload(**overrides):
    payload = {
        "thread_id": None,
        "title": "Hello",
        "body": prose_doc("Hi there"),
    }
    payload.update(overrides)
    return payload


class TestCreatePost:
    async def test_create_post_requires_auth(self, client, create):
        thread = await create(ThreadFactory)

        response = await client.post(
            "/posts", json=new_post_payload(thread_id=thread.id)
        )

        assert response.status_code == 403

    async def test_create_post(self, authed_client, create):
        client, _user = authed_client
        thread = await create(ThreadFactory)

        response = await client.post(
            "/posts", json=new_post_payload(thread_id=thread.id)
        )

        assert response.status_code == 200
        assert "id" in response.json()

    async def test_create_post_unknown_thread_returns_404(self, authed_client):
        client, _user = authed_client

        response = await client.post("/posts", json=new_post_payload(thread_id=999999))

        assert response.status_code == 404

    async def test_create_post_is_published_and_returned_by_get_posts(
        self, authed_client, create
    ):
        client, user = authed_client
        thread = await create(ThreadFactory)

        response = await client.post(
            "/posts", json=new_post_payload(thread_id=thread.id, title="A reply")
        )
        post_id = response.json()["id"]

        list_response = await client.get("/posts", params={"thread_id": thread.id})

        body = list_response.json()
        assert [p["id"] for p in body["posts"]] == [post_id]
        assert body["posts"][0]["title"] == "A reply"
        assert body["posts"][0]["author"]["id"] == user.id
        assert body["count"] == 1

    async def test_create_post_attaches_to_thread(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        thread = await create(ThreadFactory)

        response = await client.post(
            "/posts", json=new_post_payload(thread_id=thread.id)
        )
        post_id = response.json()["id"]

        await db_session.refresh(thread)
        assert thread.first_post_id == post_id
        assert thread.last_post_id == post_id
        assert thread.post_count == 1

    async def test_create_post_on_locked_thread_returns_403(
        self, authed_client, create
    ):
        client, _user = authed_client
        thread = await create(ThreadFactory, options=Thread.Options(locked=True))

        response = await client.post(
            "/posts", json=new_post_payload(thread_id=thread.id)
        )

        assert response.status_code == 403
