from datetime import UTC, datetime, timedelta

import pytest

from app.repositories.read_tracking_repository import ReadTrackingRepository
from app.repositories.thread_repository import ThreadRepository
from tests.factories import ForumFactory, PostFactory, ThreadFactory, UserFactory

NOW = datetime.now(UTC)
SINCE = NOW - timedelta(days=7)


def ago(**delta) -> datetime:
    return NOW - timedelta(**delta)


class TestGetRecent:
    @pytest.fixture
    async def user(self, create):
        return await create(UserFactory)

    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint, user):
        return ThreadRepository(db_session, principal=user)

    @pytest.fixture
    async def forum(self, create, wrap_in_savepoint):
        return await create(ForumFactory, heritage=[])

    @pytest.fixture
    def make_thread(self, create, repository):
        async def _make_thread(forum, last_post_at=None, **kwargs):
            thread = await create(ThreadFactory, forum=forum, **kwargs)
            if last_post_at is not None:
                post = await create(
                    PostFactory, thread=thread, published_at=last_post_at
                )
                await repository.attach_new_post(thread, post)
            return thread

        return _make_thread

    async def test_keeps_threads_in_window_newest_first(
        self, repository, forum, make_thread
    ):
        older = await make_thread(forum, ago(days=3))
        newest = await make_thread(forum, ago(hours=1))
        await make_thread(forum, ago(days=8))
        await make_thread(forum)  # no published post

        threads, count = await repository.get_recent([forum.id], SINCE)

        assert [t.id for t in threads] == [newest.id, older.id]
        assert count == 2

    async def test_equal_last_posts_order_by_newest_thread(
        self, repository, forum, make_thread
    ):
        moment = ago(days=1)
        first = await make_thread(forum, moment)
        second = await make_thread(forum, moment)

        threads, _ = await repository.get_recent([forum.id], SINCE)

        assert [t.id for t in threads] == [second.id, first.id]

    async def test_only_given_forums_and_live_threads(
        self, repository, create, forum, make_thread
    ):
        other = await create(ForumFactory, heritage=[])
        kept = await make_thread(forum, ago(days=1))
        await make_thread(other, ago(days=1))
        await make_thread(forum, ago(days=1), deleted=ago(hours=1))

        threads, count = await repository.get_recent([forum.id], SINCE)

        assert [t.id for t in threads] == [kept.id]
        assert count == 1

    async def test_no_forums_returns_nothing(self, repository):
        assert await repository.get_recent([], SINCE) == ([], 0)

    async def test_pages_report_the_full_count(self, repository, forum, make_thread):
        threads = [await make_thread(forum, ago(days=day)) for day in (1, 2, 3)]

        page_two, count = await repository.get_recent(
            [forum.id], SINCE, page=2, limit=2
        )

        assert [t.id for t in page_two] == [threads[2].id]
        assert count == 3


class TestGetRecentUnread:
    @pytest.fixture
    async def user(self, create):
        return await create(UserFactory)

    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint, user):
        return ThreadRepository(db_session, principal=user)

    @pytest.fixture
    async def read_tracking(self, db_session, user):
        return ReadTrackingRepository(db_session, principal=user)

    @pytest.fixture
    async def parent(self, create, wrap_in_savepoint):
        return await create(ForumFactory, heritage=[])

    @pytest.fixture
    async def child(self, create, parent):
        return await create(ForumFactory, heritage=[parent.id], parent_id=parent.id)

    @pytest.fixture
    def make_thread(self, create, repository):
        async def _make_thread(forum, last_post_at):
            thread = await create(ThreadFactory, forum=forum)
            post = await create(PostFactory, thread=thread, published_at=last_post_at)
            await repository.attach_new_post(thread, post)
            return thread

        return _make_thread

    async def unread_ids(self, repository, *forums) -> list[int]:
        threads, _ = await repository.get_recent(
            [forum.id for forum in forums], SINCE, unread_only=True
        )
        return [thread.id for thread in threads]

    async def test_thread_read_up_to_its_last_post_is_left_out(
        self, repository, read_tracking, parent, make_thread
    ):
        unread = await make_thread(parent, ago(days=1))
        read = await make_thread(parent, ago(days=2))
        await read_tracking.mark_thread_read(read)

        assert await self.unread_ids(repository, parent) == [unread.id]

    async def test_new_post_after_the_read_point_makes_it_unread_again(
        self, repository, read_tracking, parent, make_thread, create
    ):
        thread = await make_thread(parent, ago(days=2))
        await read_tracking.mark_thread_read(thread)
        post = await create(PostFactory, thread=thread, published_at=ago(hours=1))
        await repository.attach_new_post(thread, post)

        assert await self.unread_ids(repository, parent) == [thread.id]

    async def test_forum_mark_read_covers_subforums_but_not_newer_posts(
        self, repository, read_tracking, parent, child, make_thread
    ):
        await make_thread(parent, ago(days=2))
        await make_thread(child, ago(days=1))
        await read_tracking.mark_forum_read(parent)
        newer = await make_thread(child, ago(minutes=1))

        assert await self.unread_ids(repository, parent, child) == [newer.id]

    async def test_marked_unread_thread_survives_a_forum_mark_read(
        self, repository, read_tracking, parent, make_thread
    ):
        pinned = await make_thread(parent, ago(days=2))
        await read_tracking.mark_forum_read(parent)
        await read_tracking.mark_thread_unread(pinned)

        assert await self.unread_ids(repository, parent) == [pinned.id]

    async def test_count_matches_the_unread_threads(
        self, repository, read_tracking, parent, make_thread
    ):
        await make_thread(parent, ago(days=1))
        await make_thread(parent, ago(days=2))
        read = await make_thread(parent, ago(days=3))
        await read_tracking.mark_thread_read(read)

        threads, count = await repository.get_recent(
            [parent.id], SINCE, page=1, limit=1, unread_only=True
        )

        assert len(threads) == 1
        assert count == 2
