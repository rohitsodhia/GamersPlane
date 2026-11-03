from sqlalchemy import select

from app.models import Event, EventRecipient, RolePermission
from tests.factories import ActivatedUserFactory
from tests.factories.prose import mentioning_doc

Verbs = RolePermission.ValidPermissions


class TestRoutesSyncMentions:
    async def test_a_new_post_notifies_the_mentioned_user(
        self, authed_client, create, thread, db_session
    ):
        client, _ = authed_client
        mentioned = await create(ActivatedUserFactory)

        response = await client.post(
            "/posts",
            json={
                "thread_id": thread.id,
                "title": "Hi",
                "body": mentioning_doc(mentioned.id),
            },
        )

        assert response.status_code == 200
        post_id = response.json()["id"]
        event = await db_session.scalar(select(Event).where(Event.post_id == post_id))
        rows = await db_session.scalars(
            select(EventRecipient.user_id).where(EventRecipient.event_id == event.id)
        )
        assert rows.all() == [mentioned.id]

    async def test_a_new_thread_notifies_from_its_first_post(
        self, authed_client, create, thread, db_session
    ):
        client, user = authed_client
        mentioned = await create(ActivatedUserFactory)

        response = await client.post(
            "/threads",
            json={
                "forum_id": thread.forum_id,
                "title": "Hi",
                "body": mentioning_doc(mentioned.id),
            },
        )

        assert response.status_code == 200
        thread_id = response.json()["id"]
        event = await db_session.scalar(
            select(Event).where(Event.thread_id == thread_id)
        )
        assert event.actor_id == user.id
        rows = await db_session.scalars(
            select(EventRecipient.user_id).where(EventRecipient.event_id == event.id)
        )
        assert rows.all() == [mentioned.id]

    async def test_a_minor_edit_still_syncs_both_ways(
        self, authed_client, create, thread, make_post, db_session
    ):
        client, user = authed_client
        kept = await create(ActivatedUserFactory)
        dropped = await create(ActivatedUserFactory)
        added = await create(ActivatedUserFactory)
        post = await make_post(thread, user, mentioning_doc(kept.id, dropped.id))
        await client.patch(
            f"/posts/{post.id}",
            json={"title": "Hi", "body": mentioning_doc(kept.id, dropped.id)},
        )

        response = await client.patch(
            f"/posts/{post.id}",
            json={
                "title": "Hi",
                "body": mentioning_doc(kept.id, added.id),
                "minor_edit": True,
            },
        )

        assert response.status_code == 200
        event = await db_session.scalar(select(Event).where(Event.post_id == post.id))
        rows = await db_session.scalars(
            select(EventRecipient.user_id).where(EventRecipient.event_id == event.id)
        )
        assert set(rows) == {kept.id, added.id}

    async def test_a_moderators_edit_still_notifies_as_the_author(
        self, authed_client, create, thread, make_post, grant, db_session
    ):
        client, moderator = authed_client
        await grant(moderator, thread.forum, Verbs.FORUM_MODERATE)
        author = await create(ActivatedUserFactory)
        mentioned = await create(ActivatedUserFactory)
        post = await make_post(thread, author, mentioning_doc())

        response = await client.patch(
            f"/posts/{post.id}",
            json={"title": "Hi", "body": mentioning_doc(mentioned.id)},
        )

        assert response.status_code == 200
        event = await db_session.scalar(select(Event).where(Event.post_id == post.id))
        assert event.actor_id == author.id
