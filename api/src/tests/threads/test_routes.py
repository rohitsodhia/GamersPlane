from tests.factories import ForumFactory, PostFactory, ThreadFactory


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

    async def test_get_threads_requires_forum_id(self, client):
        response = await client.get("/threads")

        assert response.status_code == 422

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
