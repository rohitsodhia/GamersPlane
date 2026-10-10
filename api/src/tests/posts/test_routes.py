from datetime import UTC, datetime

from app.configs import configs
from app.models import Post, RolePermission, Thread
from app.repositories import PostRepository, ThreadRepository
from tests.factories import (
    ForumFactory,
    PostFactory,
    RoleFactory,
    ThreadFactory,
    UserFactory,
    prose_doc,
)

Verbs = RolePermission.ValidPermissions


WEBHOOK_URL = "https://discord.com/api/webhooks/123456789/abc-DEF_123"


async def grant(db_session, user, forum, *verbs):
    """Give ``user`` a role holding ``verbs`` on ``forum``."""
    role = RoleFactory.build()
    db_session.add(role)
    for verb in verbs:
        role.grant(verb, scope_type=RolePermission.ScopeTypes.FORUM, scope_id=forum.id)
    role.users.append(user)
    await db_session.flush()


async def closed_thread(create, **kwargs):
    """A thread in a forum outside the site root, so no default grants reach it."""
    forum = await create(ForumFactory, heritage=[])
    return await create(ThreadFactory, forum=forum, **kwargs)


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
        assert author["avatar"] == f"{configs.AVATARS_ROOT}/users/avatar.png"

    async def test_get_posts_in_unreadable_forum_returns_404(self, client, create):
        thread = await closed_thread(create)

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert response.status_code == 404


class TestGetPost:
    async def test_get_post_requires_auth(self, client, create):
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread)

        response = await client.get(f"/posts/{post.id}")

        assert response.status_code == 403

    async def test_get_post_unknown_post_returns_404(self, authed_client):
        client, _user = authed_client

        response = await client.get("/posts/999999")

        assert response.status_code == 404

    async def test_get_post_returns_post(self, authed_client, create):
        client, _user = authed_client
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread, title="Hello")

        response = await client.get(f"/posts/{post.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == post.id
        assert body["title"] == "Hello"
        assert body["body"] == post.body

    async def test_get_post_returns_datestamp_for_published_post(
        self, authed_client, create
    ):
        client, _user = authed_client
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread)

        response = await client.get(f"/posts/{post.id}")

        assert response.json()["datestamp"] is not None

    async def test_get_post_returns_null_datestamp_for_draft_post(
        self, authed_client, create
    ):
        client, _user = authed_client
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread, state=Post.States.DRAFT)

        response = await client.get(f"/posts/{post.id}")

        assert response.status_code == 200
        assert response.json()["datestamp"] is None

    async def test_get_post_returns_thread_forum_page_and_is_first_post(
        self, authed_client, create
    ):
        client, _user = authed_client
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread)
        thread.first_post_id = post.id

        response = await client.get(f"/posts/{post.id}")

        body = response.json()
        assert body["thread_id"] == thread.id
        assert body["forum_id"] == thread.forum_id
        assert body["page"] == 1
        assert body["is_first_post"] is True

    async def test_get_post_returns_discord_webhook_to_first_post_author(
        self, authed_client, create
    ):
        client, user = authed_client
        thread = await create(
            ThreadFactory, options=Thread.Options(discord_webhook=WEBHOOK_URL)
        )
        post = await create(PostFactory, thread=thread, author=user)
        thread.first_post_id = post.id

        response = await client.get(f"/posts/{post.id}")

        assert response.json()["discord_webhook"] == WEBHOOK_URL

    async def test_get_post_hides_discord_webhook_on_non_first_post(
        self, authed_client, create
    ):
        client, user = authed_client
        thread = await create(
            ThreadFactory, options=Thread.Options(discord_webhook=WEBHOOK_URL)
        )
        first_post = await create(PostFactory, thread=thread)
        thread.first_post_id = first_post.id
        reply = await create(PostFactory, thread=thread, author=user)

        response = await client.get(f"/posts/{reply.id}")

        assert response.json()["discord_webhook"] is None

    async def test_get_post_hides_discord_webhook_from_moderator_who_is_not_author(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread = await create(
            ThreadFactory, options=Thread.Options(discord_webhook=WEBHOOK_URL)
        )
        post = await create(PostFactory, thread=thread)
        thread.first_post_id = post.id
        await grant(db_session, user, thread.forum, Verbs.FORUM_MODERATE)

        response = await client.get(f"/posts/{post.id}")

        assert response.status_code == 200
        assert response.json()["discord_webhook"] is None

    async def test_get_post_in_unreadable_forum_returns_404(
        self, authed_client, create
    ):
        client, _user = authed_client
        post = await create(PostFactory, thread=await closed_thread(create))

        response = await client.get(f"/posts/{post.id}")

        assert response.status_code == 404


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

    async def test_create_post_is_read_for_its_author(
        self, authed_client, create, db_session
    ):
        client, _user = authed_client
        thread = await create(ThreadFactory)
        earlier = await create(
            PostFactory, thread=thread, published_at=datetime(2020, 1, 1, tzinfo=UTC)
        )
        await ThreadRepository(db_session, principal=None).attach_new_post(
            thread, earlier
        )
        params = {"forum_id": thread.forum_id}
        before = await client.get("/threads", params=params)
        assert before.json()["threads"][0]["has_unread"] is True

        await client.post("/posts", json=new_post_payload(thread_id=thread.id))

        after = await client.get("/threads", params=params)
        assert after.json()["threads"][0]["has_unread"] is False

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

    async def test_create_post_without_write_permission_returns_403(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread = await closed_thread(create)
        await grant(db_session, user, thread.forum, Verbs.FORUM_READ)

        response = await client.post(
            "/posts", json=new_post_payload(thread_id=thread.id)
        )

        assert response.status_code == 403

    async def test_moderator_can_post_in_locked_thread(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread = await closed_thread(create, options=Thread.Options(locked=True))
        await grant(db_session, user, thread.forum, Verbs.FORUM_MODERATE)

        response = await client.post(
            "/posts", json=new_post_payload(thread_id=thread.id)
        )

        assert response.status_code == 200


def edit_post_payload(**overrides):
    payload = {
        "title": "Updated Title",
        "body": prose_doc("Updated body"),
    }
    payload.update(overrides)
    return payload


class TestEditPost:
    async def test_edit_post_requires_auth(self, client, create):
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread)

        response = await client.patch(f"/posts/{post.id}", json=edit_post_payload())

        assert response.status_code == 403

    async def test_edit_post_updates_title_and_body(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread, author=user)
        new_body = prose_doc("New body content")

        response = await client.patch(
            f"/posts/{post.id}",
            json=edit_post_payload(title="New Title", body=new_body),
        )

        assert response.status_code == 200
        assert response.json()["id"] == post.id
        await db_session.refresh(post)
        assert post.title == "New Title"
        assert post.body == new_body

    async def test_edit_post_unknown_post_returns_404(self, authed_client):
        client, _user = authed_client

        response = await client.patch("/posts/999999", json=edit_post_payload())

        assert response.status_code == 404

    async def test_edit_post_not_author_returns_403(self, authed_client, create):
        client, _user = authed_client
        thread = await create(ThreadFactory)
        other_author = await create(UserFactory)
        post = await create(PostFactory, thread=thread, author=other_author)

        response = await client.patch(f"/posts/{post.id}", json=edit_post_payload())

        assert response.status_code == 403

    async def test_edit_post_on_locked_thread_returns_403(self, authed_client, create):
        client, user = authed_client
        thread = await create(ThreadFactory, options=Thread.Options(locked=True))
        post = await create(PostFactory, thread=thread, author=user)

        response = await client.patch(f"/posts/{post.id}", json=edit_post_payload())

        assert response.status_code == 403

    async def test_edit_own_post_without_edit_permission_returns_403(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread = await closed_thread(create)
        await grant(db_session, user, thread.forum, Verbs.FORUM_READ)
        post = await create(PostFactory, thread=thread, author=user)

        response = await client.patch(f"/posts/{post.id}", json=edit_post_payload())

        assert response.status_code == 403

    async def test_moderator_can_edit_others_posts_in_locked_thread(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread = await closed_thread(create, options=Thread.Options(locked=True))
        await grant(db_session, user, thread.forum, Verbs.FORUM_MODERATE)
        post = await create(
            PostFactory, thread=thread, author=await create(UserFactory)
        )

        response = await client.patch(f"/posts/{post.id}", json=edit_post_payload())

        assert response.status_code == 200


class TestEditPostThreadOptions:
    async def thread_with_posts(self, create, db_session, user):
        """A thread with a first post and a reply, both by ``user``."""
        thread = await create(ThreadFactory)
        first = await create(PostFactory, thread=thread, author=user)
        reply = await create(PostFactory, thread=thread, author=user)
        thread.first_post_id = first.id
        await db_session.flush()
        return thread, first, reply

    async def test_thread_options_on_a_reply_returns_400(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread, _first, reply = await self.thread_with_posts(create, db_session, user)

        response = await client.patch(
            f"/posts/{reply.id}",
            json=edit_post_payload(thread_options={"sticky": False}),
        )

        assert response.status_code == 400

    async def test_first_post_edit_can_enable_rolls_and_add_one(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread, first, _reply = await self.thread_with_posts(create, db_session, user)
        await grant(db_session, user, thread.forum, Verbs.FORUM_ADD_ROLLS)

        response = await client.patch(
            f"/posts/{first.id}",
            json=edit_post_payload(
                thread_options={"allow_rolls": True},
                rolls=[{"type": "basic", "roll": "1d20", "reason": "Init"}],
            ),
        )

        assert response.status_code == 200
        await db_session.refresh(thread)
        assert thread.options.allow_rolls is True
        rolls = (
            await PostRepository(db_session, principal=user).get_rolls([first.id])
        )[first.id]
        assert [roll.reason for roll in rolls] == ["Init"]

    async def test_forbidden_option_change_returns_403_and_keeps_the_post(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread, first, _reply = await self.thread_with_posts(create, db_session, user)
        original_title = first.title

        response = await client.patch(
            f"/posts/{first.id}",
            json=edit_post_payload(thread_options={"locked": True}),
        )

        assert response.status_code == 403
        await db_session.refresh(first)
        await db_session.refresh(thread)
        assert first.title == original_title
        assert thread.options.locked is False


class TestDeletePost:
    async def test_delete_post_requires_auth(self, client, create):
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread)

        response = await client.delete(f"/posts/{post.id}")

        assert response.status_code == 403

    async def test_delete_post_unknown_post_returns_404(self, authed_client):
        client, _user = authed_client

        response = await client.delete("/posts/999999")

        assert response.status_code == 404

    async def test_delete_post_not_author_returns_403(self, authed_client, create):
        client, _user = authed_client
        thread = await create(ThreadFactory)
        other_author = await create(UserFactory)
        post = await create(PostFactory, thread=thread, author=other_author)

        response = await client.delete(f"/posts/{post.id}")

        assert response.status_code == 403

    async def test_delete_post_on_locked_thread_returns_403(
        self, authed_client, create
    ):
        client, user = authed_client
        thread = await create(ThreadFactory, options=Thread.Options(locked=True))
        post = await create(PostFactory, thread=thread, author=user)

        response = await client.delete(f"/posts/{post.id}")

        assert response.status_code == 403

    async def test_delete_reply_returns_204_and_soft_deletes_it(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread_repository = ThreadRepository(db_session, principal=None)
        thread = await create(ThreadFactory)
        first_post = await create(PostFactory, thread=thread)
        await thread_repository.attach_new_post(thread, first_post)
        reply = await create(PostFactory, thread=thread, author=user)
        await thread_repository.attach_new_post(thread, reply)

        response = await client.delete(f"/posts/{reply.id}")

        assert response.status_code == 204
        post_repository = PostRepository(db_session, principal=None)
        found = await post_repository.get(reply.id)
        assert found is None

    async def test_delete_reply_does_not_delete_thread(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread_repository = ThreadRepository(db_session, principal=None)
        thread = await create(ThreadFactory)
        first_post = await create(PostFactory, thread=thread)
        await thread_repository.attach_new_post(thread, first_post)
        reply = await create(PostFactory, thread=thread, author=user)
        await thread_repository.attach_new_post(thread, reply)

        await client.delete(f"/posts/{reply.id}")

        found = await thread_repository.get(thread.id)
        assert found.deleted is None

    async def test_delete_first_post_deletes_thread(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread_repository = ThreadRepository(db_session, principal=None)
        thread = await create(ThreadFactory)
        first_post = await create(PostFactory, thread=thread, author=user)
        await thread_repository.attach_new_post(thread, first_post)

        response = await client.delete(f"/posts/{first_post.id}")

        assert response.status_code == 204
        found = await thread_repository.get(thread.id)
        assert found.deleted is not None

    async def test_deleting_first_post_needs_delete_thread_not_delete(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        thread_repository = ThreadRepository(db_session, principal=None)
        thread = await closed_thread(create)
        await grant(
            db_session, user, thread.forum, Verbs.FORUM_READ, Verbs.FORUM_DELETE
        )
        first_post = await create(PostFactory, thread=thread, author=user)
        await thread_repository.attach_new_post(thread, first_post)
        reply = await create(PostFactory, thread=thread, author=user)
        await thread_repository.attach_new_post(thread, reply)

        first_response = await client.delete(f"/posts/{first_post.id}")
        reply_response = await client.delete(f"/posts/{reply.id}")

        assert first_response.status_code == 403
        assert reply_response.status_code == 204
