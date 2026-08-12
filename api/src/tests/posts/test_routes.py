from app.configs import configs
from tests.factories import PostFactory, ThreadFactory, UserFactory


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
