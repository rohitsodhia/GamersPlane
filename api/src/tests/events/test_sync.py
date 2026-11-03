from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.events.functions import sync_post_mentions
from app.models import Event, EventRecipient, Post, RolePermission
from tests.factories import ActivatedUserFactory, ForumFactory, ThreadFactory
from tests.factories.prose import mentioning_doc

Verbs = RolePermission.ValidPermissions


async def sync(db_session, post):
    await sync_post_mentions(db_session, post, post.thread, post.thread.forum)


@pytest.fixture
async def mentioned(create):
    return await create(ActivatedUserFactory)


class TestWhoIsNotified:
    async def test_a_mentioned_user_gets_a_row_on_the_authors_event(
        self, create, db_session, author, thread, make_post, mentioned
    ):
        post = await make_post(thread, author, mentioning_doc(mentioned.id))

        await sync(db_session, post)

        event = await db_session.scalar(select(Event))
        assert (event.type, event.actor_id, event.post_id, event.thread_id) == (
            Event.Types.MENTION,
            author.id,
            post.id,
            thread.id,
        )
        recipient = await db_session.scalar(select(EventRecipient))
        assert (recipient.event_id, recipient.user_id, recipient.read_at) == (
            event.id,
            mentioned.id,
            None,
        )

    async def test_the_author_mentioning_themself_creates_nothing(
        self, db_session, author, thread, make_post, recipients
    ):
        post = await make_post(thread, author, mentioning_doc(author.id))

        await sync(db_session, post)

        assert await recipients(post) is None

    async def test_a_user_who_does_not_exist_is_skipped(
        self, db_session, author, thread, make_post, mentioned, recipients
    ):
        post = await make_post(thread, author, mentioning_doc(987654, mentioned.id))

        await sync(db_session, post)

        assert await recipients(post) == {mentioned.id}

    async def test_a_user_who_cannot_read_the_forum_is_skipped(
        self, create, db_session, author, make_post, grant, mentioned, recipients
    ):
        closed = await create(ForumFactory, heritage=[])
        thread = await create(ThreadFactory, forum=closed)
        locked_out = await create(ActivatedUserFactory)
        await grant(mentioned, closed, Verbs.FORUM_READ)
        post = await make_post(
            thread, author, mentioning_doc(mentioned.id, locked_out.id)
        )

        await sync(db_session, post)

        assert await recipients(post) == {mentioned.id}

    async def test_banned_and_suspended_users_are_skipped(
        self, create, db_session, author, thread, make_post, mentioned, recipients
    ):
        banned = await create(ActivatedUserFactory)
        banned.banned = datetime.now(UTC)
        suspended = await create(ActivatedUserFactory)
        suspended.suspended_until = datetime.now(UTC) + timedelta(days=1)
        was_suspended = await create(ActivatedUserFactory)
        was_suspended.suspended_until = datetime.now(UTC) - timedelta(days=1)
        post = await make_post(
            thread,
            author,
            mentioning_doc(banned.id, suspended.id, was_suspended.id, mentioned.id),
        )

        await sync(db_session, post)

        assert await recipients(post) == {was_suspended.id, mentioned.id}

    async def test_an_unpublished_post_notifies_nobody(
        self, db_session, author, thread, make_post, mentioned, recipients
    ):
        post = await make_post(
            thread, author, mentioning_doc(mentioned.id), state=Post.States.DRAFT
        )

        await sync(db_session, post)

        assert await recipients(post) is None


class TestEdits:
    async def test_an_edit_adds_new_mentions_and_keeps_the_old(
        self, create, db_session, author, thread, make_post, mentioned, recipients
    ):
        newcomer = await create(ActivatedUserFactory)
        post = await make_post(thread, author, mentioning_doc(mentioned.id))
        await sync(db_session, post)

        post.body = mentioning_doc(mentioned.id, newcomer.id)
        await sync(db_session, post)

        assert await recipients(post) == {mentioned.id, newcomer.id}
        assert len((await db_session.scalars(select(Event))).all()) == 1

    async def test_an_edit_that_removes_a_mention_retracts_that_row(
        self, create, db_session, author, thread, make_post, mentioned, recipients
    ):
        other = await create(ActivatedUserFactory)
        post = await make_post(thread, author, mentioning_doc(mentioned.id, other.id))
        await sync(db_session, post)

        post.body = mentioning_doc(other.id)
        await sync(db_session, post)

        assert await recipients(post) == {other.id}

    async def test_removing_the_last_mention_deletes_the_event(
        self, db_session, author, thread, make_post, mentioned, recipients
    ):
        post = await make_post(thread, author, mentioning_doc(mentioned.id))
        await sync(db_session, post)

        post.body = mentioning_doc()
        await sync(db_session, post)

        assert await recipients(post) is None
        assert (await db_session.scalars(select(EventRecipient))).all() == []

    async def test_a_kept_mention_is_not_duplicated_or_reset_when_read(
        self, db_session, author, thread, make_post, mentioned
    ):
        post = await make_post(thread, author, mentioning_doc(mentioned.id))
        await sync(db_session, post)
        read_at = datetime(2026, 1, 1, tzinfo=UTC)
        (await db_session.scalar(select(EventRecipient))).read_at = read_at
        await db_session.flush()

        await sync(db_session, post)

        rows = (await db_session.scalars(select(EventRecipient))).all()
        assert [(row.user_id, row.read_at) for row in rows] == [(mentioned.id, read_at)]

    async def test_a_user_who_lost_access_keeps_their_row_through_an_edit(
        self, create, db_session, author, make_post, grant, mentioned, recipients
    ):
        closed = await create(ForumFactory, heritage=[])
        thread = await create(ThreadFactory, forum=closed)
        other = await create(ActivatedUserFactory)
        await grant(mentioned, closed, Verbs.FORUM_READ)
        post = await make_post(thread, author, mentioning_doc(mentioned.id))
        await sync(db_session, post)
        # Their access is revoked, and an unrelated edit follows.
        for role in list(mentioned.roles):
            mentioned.roles.remove(role)
        await db_session.flush()

        post.body = mentioning_doc(mentioned.id, other.id)
        await sync(db_session, post)

        assert await recipients(post) == {mentioned.id}
