from datetime import UTC, datetime, timedelta

import pytest

from app.forum_subscriptions.functions import Trigger, select_recipients
from app.models import ForumRead, ForumSubscriptionNotice, Post, ThreadRead
from app.repositories import ForumSubscriptionRepository
from tests.factories import (
    ActivatedUserFactory,
    ForumFactory,
    PostFactory,
    ThreadFactory,
    UserFactory,
)
from tests.forum_subscriptions.conftest import Verbs

NOTICED = datetime(2026, 1, 1, tzinfo=UTC)


async def recipients_for(db_session, thread, post, actor, trigger=Trigger.NEW_POST):
    found = await select_recipients(
        db_session, thread, thread.forum, post, actor, trigger
    )
    return {recipient.user_id: recipient for recipient in found}


@pytest.fixture
async def setup(create, make_thread):
    """A thread by an author, with a reply by the actor (who acts in the test)."""
    author = await create(ActivatedUserFactory)
    thread, _first = await make_thread(author)
    actor = await create(ActivatedUserFactory)
    reply = await create(PostFactory, thread=thread, author=actor)
    return thread, reply, actor


class TestModes:
    async def test_by_mode_with_a_missing_row_reading_as_new_content(
        self, create, db_session, setup, subscribe, set_mode
    ):
        thread, reply, actor = setup
        users = {}
        for mode in ("all", "new content", "none", None):
            users[mode] = await create(ActivatedUserFactory)
            await subscribe(users[mode], thread=thread)
            if mode:
                await set_mode(users[mode], mode)

        found = await recipients_for(db_session, thread, reply, actor)

        assert {recipient.mode for recipient in found.values()} == {
            "all",
            "new content",
        }
        assert set(found) == {users["all"].id, users["new content"].id, users[None].id}

    async def test_edit_reaches_only_all_subscribers(
        self, create, db_session, setup, subscribe, set_mode
    ):
        thread, reply, actor = setup
        everything = await create(ActivatedUserFactory)
        new_content = await create(ActivatedUserFactory)
        await subscribe(everything, thread=thread)
        await subscribe(new_content, thread=thread)
        await set_mode(everything, "all")

        found = await recipients_for(db_session, thread, reply, actor, Trigger.EDIT)

        assert set(found) == {everything.id}

    async def test_unpublished_post_emails_nobody(
        self, create, db_session, setup, subscribe, set_mode
    ):
        state = Post.States.DRAFT
        thread, _reply, actor = setup
        subscriber = await create(ActivatedUserFactory)
        await subscribe(subscriber, thread=thread)
        await set_mode(subscriber, "all")
        unpublished = await create(
            PostFactory, thread=thread, author=actor, state=state
        )

        assert await recipients_for(db_session, thread, unpublished, actor) == {}


class TestWhoIsConsidered:
    async def test_deleted_thread_emails_nobody(
        self, create, db_session, setup, subscribe, set_mode
    ):
        thread, reply, actor = setup
        subscriber = await create(ActivatedUserFactory)
        await subscribe(subscriber, thread=thread)
        await set_mode(subscriber, "all")
        thread.deleted = datetime.now(UTC)
        await db_session.flush()

        assert await recipients_for(db_session, thread, reply, actor) == {}

    async def test_the_actor_is_never_a_recipient(
        self, db_session, setup, subscribe, set_mode
    ):
        thread, reply, actor = setup
        await subscribe(actor, thread=thread)
        await set_mode(actor, "all")

        assert await recipients_for(db_session, thread, reply, actor) == {}

    async def test_thread_and_forum_subscription_is_one_thread_recipient(
        self, create, db_session, setup, subscribe
    ):
        thread, reply, actor = setup
        both = await create(ActivatedUserFactory)
        forum_only = await create(ActivatedUserFactory)
        await subscribe(both, thread=thread)
        await subscribe(both, forum=thread.forum)
        await subscribe(forum_only, forum=thread.forum)

        found = await recipients_for(db_session, thread, reply, actor)

        assert {uid: r.kind for uid, r in found.items()} == {
            both.id: "thread",
            forum_only.id: "forum",
        }

    async def test_a_parent_forum_subscription_does_not_reach_a_subforum_thread(
        self, create, make_thread, db_session, subscribe
    ):
        parent = await create(ForumFactory, heritage=[0])
        child = await create(ForumFactory, heritage=[0, parent.id], parent_id=parent.id)
        author = await create(ActivatedUserFactory)
        thread, _first = await make_thread(author, forum=child)
        reply = await create(PostFactory, thread=thread, author=author)
        subscriber = await create(ActivatedUserFactory)
        await subscribe(subscriber, forum=parent)

        assert await recipients_for(db_session, thread, reply, author) == {}

    async def test_drops_subscribers_who_can_no_longer_read_the_forum(
        self, create, make_thread, db_session, subscribe, grant
    ):
        closed = await create(ForumFactory, heritage=[])
        author = await create(ActivatedUserFactory)
        thread, _first = await make_thread(author, forum=closed)
        reply = await create(PostFactory, thread=thread, author=author)
        allowed = await create(ActivatedUserFactory)
        locked_out = await create(ActivatedUserFactory)
        await grant(allowed, closed, Verbs.FORUM_READ)
        await subscribe(allowed, thread=thread)
        await subscribe(locked_out, thread=thread)

        found = await recipients_for(db_session, thread, reply, author)

        assert set(found) == {allowed.id}

    async def test_skips_users_who_cannot_be_mailed(
        self, create, db_session, setup, subscribe
    ):
        thread, reply, actor = setup
        ok = await create(ActivatedUserFactory)
        banned = await create(ActivatedUserFactory)
        banned.banned = datetime.now(UTC)
        suspended = await create(ActivatedUserFactory)
        suspended.suspended_until = datetime.now(UTC) + timedelta(days=1)
        unactivated = await create(UserFactory)
        was_suspended = await create(ActivatedUserFactory)
        was_suspended.suspended_until = datetime.now(UTC) - timedelta(days=1)
        for user in (ok, banned, suspended, unactivated, was_suspended):
            await subscribe(user, thread=thread)

        found = await recipients_for(db_session, thread, reply, actor)

        assert set(found) == {ok.id, was_suspended.id}


class TestUsersDueNotice:
    """A "new content" subscriber is due another email if never mailed about the
    thread, or if they've since read what the last one covered."""

    @pytest.fixture
    async def user(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def thread(self, create, make_thread):
        author = await create(ActivatedUserFactory)
        thread, _first = await make_thread(author)
        return thread

    @pytest.fixture
    async def noticed(self, db_session, user, thread):
        db_session.add(
            ForumSubscriptionNotice(
                user_id=user.id,
                thread_id=thread.id,
                notified_at=NOTICED + timedelta(minutes=1),
                notified_through=NOTICED,
            )
        )
        await db_session.flush()

    async def due(self, db_session, thread, user):
        return await ForumSubscriptionRepository(db_session).users_due_notice(
            thread, {user.id}
        )

    async def test_never_mailed_is_due(self, db_session, thread, user):
        assert await self.due(db_session, thread, user) == {user.id}

    @pytest.mark.usefixtures("noticed")
    async def test_mailed_and_not_read_is_not_due(self, db_session, thread, user):
        assert await self.due(db_session, thread, user) == set()

    @pytest.mark.usefixtures("noticed")
    async def test_read_short_of_the_noticed_post_is_not_due(
        self, db_session, thread, user
    ):
        db_session.add(
            ThreadRead(
                user_id=user.id,
                thread_id=thread.id,
                read_until=NOTICED - timedelta(seconds=1),
            )
        )
        await db_session.flush()

        assert await self.due(db_session, thread, user) == set()

    @pytest.mark.usefixtures("noticed")
    async def test_thread_read_up_to_the_noticed_post_is_due(
        self, db_session, thread, user
    ):
        db_session.add(
            ThreadRead(user_id=user.id, thread_id=thread.id, read_until=NOTICED)
        )
        await db_session.flush()

        assert await self.due(db_session, thread, user) == {user.id}

    @pytest.mark.usefixtures("noticed")
    async def test_forum_marked_read_is_due(self, db_session, thread, user):
        db_session.add(
            ForumRead(user_id=user.id, forum_id=thread.forum_id, read_until=NOTICED)
        )
        await db_session.flush()

        assert await self.due(db_session, thread, user) == {user.id}

    @pytest.mark.usefixtures("noticed")
    async def test_pinned_thread_ignores_the_forum_marker(
        self, db_session, thread, user
    ):
        db_session.add_all(
            [
                ForumRead(
                    user_id=user.id, forum_id=thread.forum_id, read_until=NOTICED
                ),
                ThreadRead(
                    user_id=user.id, thread_id=thread.id, read_until=None, pinned=True
                ),
            ]
        )
        await db_session.flush()

        assert await self.due(db_session, thread, user) == set()

    @pytest.mark.usefixtures("noticed")
    async def test_other_threads_reads_do_not_count(
        self, create, db_session, thread, user
    ):
        other = await create(ThreadFactory)
        db_session.add(
            ThreadRead(user_id=user.id, thread_id=other.id, read_until=NOTICED)
        )
        await db_session.flush()

        assert await self.due(db_session, thread, user) == set()


class TestMarkerGatesNewContentOnly:
    async def test_all_ignores_the_marker_and_new_content_obeys_it(
        self, create, db_session, setup, subscribe, set_mode
    ):
        thread, reply, actor = setup
        everything = await create(ActivatedUserFactory)
        new_content = await create(ActivatedUserFactory)
        for user in (everything, new_content):
            await subscribe(user, thread=thread)
            db_session.add(
                ForumSubscriptionNotice(
                    user_id=user.id,
                    thread_id=thread.id,
                    notified_at=NOTICED,
                    notified_through=NOTICED,
                )
            )
        await set_mode(everything, "all")
        await db_session.flush()

        found = await recipients_for(db_session, thread, reply, actor)

        assert set(found) == {everything.id}
