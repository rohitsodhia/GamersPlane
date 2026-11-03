import pytest

from app.models import Post
from tests.factories import PostFactory, ThreadFactory, UserFactory


def mention(user_id):
    return {"type": "mention", "attrs": {"userId": user_id}}


def paragraph(*nodes):
    return {"type": "paragraph", "content": list(nodes)}


def doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


def mentioning(*user_ids):
    return doc(paragraph(*(mention(user_id) for user_id in user_ids)))


def new_post(thread, body):
    return {"thread_id": thread.id, "title": "Hello", "body": body}


@pytest.fixture
async def thread(create):
    return await create(ThreadFactory)


@pytest.fixture
async def others(create):
    """Eleven users to mention."""
    return [await create(UserFactory) for _ in range(11)]


class TestWriteValidation:
    async def test_a_post_can_mention_an_existing_user(
        self, authed_client, db_session, thread, others
    ):
        client, _ = authed_client

        response = await client.post(
            "/posts", json=new_post(thread, mentioning(others[0].id))
        )

        assert response.status_code == 200
        post = await db_session.get(Post, response.json()["id"])
        assert post.body_text == f"@{others[0].username}"

    async def test_an_unknown_user_is_rejected(self, authed_client, thread):
        client, _ = authed_client

        response = await client.post(
            "/posts", json=new_post(thread, mentioning(987654))
        )

        assert response.status_code == 400

    @pytest.mark.parametrize("user_id", ["3", None, True, 0])
    async def test_a_malformed_user_id_is_rejected(
        self, authed_client, thread, user_id
    ):
        client, _ = authed_client

        response = await client.post(
            "/posts", json=new_post(thread, mentioning(user_id))
        )

        assert response.status_code == 400

    async def test_a_malformed_id_inside_a_quote_is_still_rejected(
        self, authed_client, thread
    ):
        client, _ = authed_client
        quote = {"type": "quote", "content": [paragraph(mention("x"))]}

        response = await client.post("/posts", json=new_post(thread, doc(quote)))

        assert response.status_code == 400

    async def test_ten_distinct_users_are_fine_but_eleven_are_not(
        self, authed_client, thread, others
    ):
        client, _ = authed_client
        ids = [user.id for user in others]

        ten = await client.post("/posts", json=new_post(thread, mentioning(*ids[:10])))
        eleven = await client.post("/posts", json=new_post(thread, mentioning(*ids)))

        assert ten.status_code == 200
        assert eleven.status_code == 400
        assert "10" in eleven.text

    async def test_repeating_a_user_counts_once(self, authed_client, thread, others):
        client, _ = authed_client
        ids = [user.id for user in others[:10]]

        response = await client.post(
            "/posts", json=new_post(thread, mentioning(*ids, *ids, ids[0]))
        )

        assert response.status_code == 200

    async def test_quoted_mentions_dont_count_towards_the_cap(
        self, authed_client, thread, others
    ):
        client, _ = authed_client
        ids = [user.id for user in others]
        quote = {"type": "quote", "content": [paragraph(*(mention(i) for i in ids))]}

        response = await client.post(
            "/posts", json=new_post(thread, doc(quote, paragraph(mention(ids[0]))))
        )

        assert response.status_code == 200

    async def test_a_new_thread_checks_its_mentions(
        self, authed_client, create, others
    ):
        client, _ = authed_client
        thread = await create(ThreadFactory)
        base = {"forum_id": thread.forum_id, "title": "Hello"}

        rejected = await client.post(
            "/threads", json={**base, "body": mentioning(987654)}
        )
        accepted = await client.post(
            "/threads", json={**base, "body": mentioning(others[0].id)}
        )

        assert rejected.status_code == 400
        assert accepted.status_code == 200


class TestEditValidation:
    async def test_edit_checks_and_keeps_search_text_in_step(
        self, authed_client, create, db_session, thread, others
    ):
        client, user = authed_client
        post = await create(PostFactory, thread=thread, author=user)
        edit = {"title": "Edited"}

        rejected = await client.patch(
            f"/posts/{post.id}", json={**edit, "body": mentioning(987654)}
        )
        accepted = await client.patch(
            f"/posts/{post.id}", json={**edit, "body": mentioning(others[1].id)}
        )

        assert rejected.status_code == 400
        assert accepted.status_code == 200
        await db_session.refresh(post)
        assert post.body_text == f"@{others[1].username}"


class TestContentMentionsInResponses:
    async def test_posts_list_each_mentioned_user_once_quoted_ones_too(
        self, authed_client, create, thread, others
    ):
        client, user = authed_client
        quote = {"type": "quote", "content": [paragraph(mention(others[2].id))]}
        await create(
            PostFactory,
            thread=thread,
            author=user,
            body=doc(
                paragraph(mention(others[0].id), mention(others[1].id)),
                paragraph(mention(others[0].id), mention(987654)),
                quote,
            ),
        )
        await create(PostFactory, thread=thread, author=user, body=doc(paragraph()))

        response = await client.get("/posts", params={"thread_id": thread.id})

        first, second = response.json()["posts"]
        assert first["content_mentions"] == [
            {"id": others[0].id, "username": others[0].username},
            {"id": others[1].id, "username": others[1].username},
            {"id": others[2].id, "username": others[2].username},
        ]
        assert second["content_mentions"] == []

    async def test_a_single_post_lists_its_mentions_and_follows_renames(
        self, authed_client, create, db_session, thread, others
    ):
        client, user = authed_client
        post = await create(
            PostFactory,
            thread=thread,
            author=user,
            body=mentioning(others[0].id),
        )
        others[0].username = "Renamed"
        await db_session.flush()

        response = await client.get(f"/posts/{post.id}")

        assert response.json()["content_mentions"] == [
            {"id": others[0].id, "username": "Renamed"}
        ]
