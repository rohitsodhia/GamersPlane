from sqlalchemy import func, select

from app.models import ForumSubscription
from tests.factories import ActivatedUserFactory, ForumFactory


async def count_subscriptions(db_session, user):
    return await db_session.scalar(
        select(func.count()).where(ForumSubscription.user_id == user.id)
    )


class TestForumSubscription:
    async def test_subscribe_is_idempotent_and_flags_the_forum(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[0])

        first = await client.put(f"/forums/{forum.id}/subscription")
        second = await client.put(f"/forums/{forum.id}/subscription")
        detail = await client.get(f"/forums/{forum.id}")

        assert (first.status_code, second.status_code) == (204, 204)
        assert await count_subscriptions(db_session, user) == 1
        assert detail.json()["subscribed"] is True

    async def test_flag_is_for_this_forum_and_this_user_only(
        self, authed_client, create, subscribe
    ):
        client, user = authed_client
        parent = await create(ForumFactory, heritage=[0])
        child = await create(ForumFactory, heritage=[0, parent.id], parent_id=parent.id)
        other = await create(ActivatedUserFactory)
        await subscribe(user, forum=parent)
        await subscribe(other, forum=child)

        parent_detail = await client.get(f"/forums/{parent.id}")
        child_detail = await client.get(f"/forums/{child.id}")

        assert parent_detail.json()["subscribed"] is True
        assert child_detail.json()["subscribed"] is False

    async def test_unsubscribe_is_idempotent(self, authed_client, create, subscribe):
        client, user = authed_client
        forum = await create(ForumFactory, heritage=[0])
        await subscribe(user, forum=forum)

        first = await client.delete(f"/forums/{forum.id}/subscription")
        second = await client.delete(f"/forums/{forum.id}/subscription")
        detail = await client.get(f"/forums/{forum.id}")

        assert (first.status_code, second.status_code) == (204, 204)
        assert detail.json()["subscribed"] is False

    async def test_cannot_subscribe_to_an_unreadable_forum(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        closed = await create(ForumFactory, heritage=[])

        response = await client.put(f"/forums/{closed.id}/subscription")

        assert response.status_code == 404
        assert await count_subscriptions(db_session, user) == 0

    async def test_can_unsubscribe_after_losing_access(
        self, authed_client, create, db_session, subscribe
    ):
        client, user = authed_client
        closed = await create(ForumFactory, heritage=[])
        await subscribe(user, forum=closed)

        response = await client.delete(f"/forums/{closed.id}/subscription")

        assert response.status_code == 204
        assert await count_subscriptions(db_session, user) == 0


class TestThreadSubscription:
    async def test_subscribe_is_idempotent_and_flags_the_thread(
        self, authed_client, make_thread, db_session
    ):
        client, user = authed_client
        thread, _ = await make_thread(user)

        first = await client.put(f"/threads/{thread.id}/subscription")
        second = await client.put(f"/threads/{thread.id}/subscription")
        detail = await client.get(f"/threads/{thread.id}")

        assert (first.status_code, second.status_code) == (204, 204)
        assert await count_subscriptions(db_session, user) == 1
        assert detail.json()["subscribed"] is True

    async def test_forum_subscription_does_not_flag_its_threads(
        self, authed_client, make_thread, subscribe
    ):
        client, user = authed_client
        thread, _ = await make_thread(user)
        await subscribe(user, forum=thread.forum)

        detail = await client.get(f"/threads/{thread.id}")

        assert detail.json()["subscribed"] is False

    async def test_unsubscribe_is_idempotent(
        self, authed_client, make_thread, subscribe
    ):
        client, user = authed_client
        thread, _ = await make_thread(user)
        await subscribe(user, thread=thread)

        first = await client.delete(f"/threads/{thread.id}/subscription")
        second = await client.delete(f"/threads/{thread.id}/subscription")
        detail = await client.get(f"/threads/{thread.id}")

        assert (first.status_code, second.status_code) == (204, 204)
        assert detail.json()["subscribed"] is False

    async def test_anonymous_viewer_sees_not_subscribed(
        self, client, make_thread, create
    ):
        thread, _ = await make_thread(await create(ActivatedUserFactory))

        detail = await client.get(f"/threads/{thread.id}")

        assert detail.json()["subscribed"] is False


class TestGetSubscriptions:
    async def test_lists_forums_with_ancestors_and_threads_by_forum(
        self, authed_client, create, make_thread, subscribe
    ):
        client, user = authed_client
        parent = await create(ForumFactory, title="Parent", heritage=[0], order=1)
        child = await create(
            ForumFactory,
            title="Child",
            heritage=[0, parent.id],
            parent_id=parent.id,
            order=2,
        )
        thread, _ = await make_thread(user, forum=child)
        await subscribe(user, forum=child)
        await subscribe(user, thread=thread)

        response = await client.get("/me/subscriptions")

        body = response.json()
        assert body["forums"] == [
            {
                "id": parent.id,
                "title": "Parent",
                "parent_id": None,
                "subscribed": False,
            },
            {
                "id": child.id,
                "title": "Child",
                "parent_id": parent.id,
                "subscribed": True,
            },
        ]
        assert body["thread_groups"] == [
            {
                "forum_id": child.id,
                "forum_title": "Child",
                "threads": [{"id": thread.id, "title": "Topic"}],
            }
        ]

    async def test_hides_unreadable_items_but_keeps_them_subscribed(
        self, authed_client, create, make_thread, subscribe, db_session
    ):
        client, user = authed_client
        closed = await create(ForumFactory, heritage=[])
        closed_thread, _ = await make_thread(user, forum=closed)
        await subscribe(user, forum=closed)
        await subscribe(user, thread=closed_thread)

        response = await client.get("/me/subscriptions")

        assert response.json() == {"forums": [], "thread_groups": []}
        assert await count_subscriptions(db_session, user) == 2
