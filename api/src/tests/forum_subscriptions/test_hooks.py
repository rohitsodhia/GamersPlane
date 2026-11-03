"""The post, thread and edit routes send subscription emails."""

from sqlalchemy import func, select

from app.configs import configs
from app.models import ForumSubscriptionNotice
from tests.factories import ActivatedUserFactory, ForumFactory, prose_doc

SECRET = "the secret plot twist"


def reply_payload(thread):
    return {"thread_id": thread.id, "title": "Re", "body": prose_doc(SECRET)}


def edit_payload(**overrides):
    return {"title": "Edited", "body": prose_doc(SECRET), **overrides}


class TestNewThread:
    async def test_mails_forum_subscribers_but_not_the_poster(
        self, authed_client, create, subscribe, set_mode, sent
    ):
        client, poster = authed_client
        forum = await create(ForumFactory, title="Tavern", heritage=[0])
        watcher = await create(ActivatedUserFactory)
        await subscribe(watcher, forum=forum)
        await set_mode(watcher, "all")
        await subscribe(poster, forum=forum)
        await set_mode(poster, "all")

        response = await client.post(
            "/threads",
            json={"forum_id": forum.id, "title": "Hello", "body": prose_doc(SECRET)},
        )

        assert response.status_code == 200
        [email] = sent
        assert email["bcc"] == [watcher.email]
        assert email["to"] == configs.CONTACT_EMAIL
        assert email["subject"] == "New thread in Tavern: Hello"
        assert poster.username in email["content"]
        assert SECRET not in email["content"]

    async def test_new_content_forum_subscriber_is_mailed_and_noticed(
        self, authed_client, create, subscribe, db_session, sent
    ):
        client, _poster = authed_client
        forum = await create(ForumFactory, title="Tavern", heritage=[0])
        watcher = await create(ActivatedUserFactory)
        await subscribe(watcher, forum=forum)

        response = await client.post(
            "/threads",
            json={"forum_id": forum.id, "title": "Hello", "body": prose_doc(SECRET)},
        )

        [email] = sent
        assert email["bcc"] == [watcher.email]
        assert email["subject"] == "New activity in the Tavern forum"
        notice = await db_session.scalar(
            select(ForumSubscriptionNotice).where(
                ForumSubscriptionNotice.user_id == watcher.id,
                ForumSubscriptionNotice.thread_id == response.json()["id"],
            )
        )
        assert notice is not None


class TestNewReply:
    async def test_new_content_subscriber_is_mailed_once_until_they_visit(
        self, authed_client, auth_as, create, make_thread, subscribe, set_mode, sent
    ):
        client, poster = authed_client
        thread, _first = await make_thread(poster)
        everything = await create(ActivatedUserFactory)
        new_content = await create(ActivatedUserFactory)
        await subscribe(everything, thread=thread)
        await set_mode(everything, "all")
        await subscribe(new_content, thread=thread)

        await client.post("/posts", json=reply_payload(thread))
        await client.post("/posts", json=reply_payload(thread))

        mailed = [email["bcc"] for email in sent]
        # Both on the first reply; only "all" on the second.
        assert sorted(mailed) == [
            [everything.email],
            [everything.email],
            [new_content.email],
        ]

        sent.clear()
        auth_as(new_content)
        last_post_id = (
            await client.get("/posts", params={"thread_id": thread.id})
        ).json()["posts"][-1]["id"]
        await client.post(f"/threads/{thread.id}/read", json={"post_id": last_post_id})
        auth_as(poster)
        await client.post("/posts", json=reply_payload(thread))

        assert sorted(email["bcc"] for email in sent) == [
            [everything.email],
            [new_content.email],
        ]

    async def test_reply_title_comes_from_the_first_post_and_kinds_are_separate_emails(
        self, authed_client, create, make_thread, subscribe, set_mode, sent
    ):
        client, poster = authed_client
        thread, _first = await make_thread(poster)
        by_thread = await create(ActivatedUserFactory)
        by_forum = await create(ActivatedUserFactory)
        await subscribe(by_thread, thread=thread)
        await subscribe(by_forum, forum=thread.forum)
        for user in (by_thread, by_forum):
            await set_mode(user, "all")

        await client.post("/posts", json=reply_payload(thread))

        assert sorted(email["bcc"][0] for email in sent) == sorted(
            [by_thread.email, by_forum.email]
        )
        assert len(sent) == 2
        assert all(email["subject"] == 'New post in "Topic"' for email in sent)
        assert all(SECRET not in email["content"] for email in sent)

    async def test_nothing_is_sent_or_recorded_when_email_is_disabled(
        self,
        authed_client,
        make_thread,
        create,
        subscribe,
        db_session,
        monkeypatch,
        sent,
    ):
        client, poster = authed_client
        monkeypatch.setattr(configs, "EMAIL_ENABLED", False)
        thread, _first = await make_thread(poster)
        subscriber = await create(ActivatedUserFactory)
        await subscribe(subscriber, thread=thread)

        response = await client.post("/posts", json=reply_payload(thread))

        assert response.status_code == 200
        assert sent == []
        assert (
            await db_session.scalar(select(func.count(ForumSubscriptionNotice.user_id)))
            == 0
        )


class TestEdit:
    async def test_major_edit_mails_only_all_subscribers(
        self, authed_client, create, make_thread, subscribe, set_mode, sent
    ):
        client, poster = authed_client
        thread, first = await make_thread(poster)
        everything = await create(ActivatedUserFactory)
        new_content = await create(ActivatedUserFactory)
        await subscribe(everything, thread=thread)
        await set_mode(everything, "all")
        await subscribe(new_content, thread=thread)

        response = await client.patch(f"/posts/{first.id}", json=edit_payload())

        assert response.status_code == 200
        [email] = sent
        assert email["bcc"] == [everything.email]
        assert email["subject"] == 'Post edited in "Edited"'

    async def test_minor_edit_mails_nobody(
        self, authed_client, create, make_thread, subscribe, set_mode, sent
    ):
        client, poster = authed_client
        thread, first = await make_thread(poster)
        everything = await create(ActivatedUserFactory)
        await subscribe(everything, thread=thread)
        await set_mode(everything, "all")

        response = await client.patch(
            f"/posts/{first.id}", json=edit_payload(minor_edit=True)
        )

        assert response.status_code == 200
        assert sent == []
