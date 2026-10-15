from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.models import Thread
from app.repositories.thread_repository import ThreadRepository
from tests.factories import ForumFactory, PostFactory, ThreadFactory
from tests.threads.test_search_routes import add_thread


class TestThreadRepository:
    @pytest.fixture
    async def forum(self, create, wrap_in_savepoint):
        return await create(ForumFactory, heritage=[])

    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return ThreadRepository(db_session, principal=None)

    async def test_get_all_returns_threads_for_forum(self, repository, create, forum):
        thread = await create(ThreadFactory, forum=forum)

        threads = list(await repository.get_all(forum.id))

        assert [t.id for t in threads] == [thread.id]

    async def test_get_all_excludes_other_forums(self, repository, create, forum):
        other_forum = await create(ForumFactory, heritage=[])
        await create(ThreadFactory, forum=other_forum)

        threads = list(await repository.get_all(forum.id))

        assert threads == []

    async def test_get_all_paginates_to_second_page(self, repository, create, forum):
        now = datetime.now(timezone.utc)
        threads = [
            await create(
                ThreadFactory, forum=forum, last_post_at=now - timedelta(days=days)
            )
            for days in range(3)
        ]

        page_one = list(await repository.get_all(forum.id, page=1, limit=2))
        page_two = list(await repository.get_all(forum.id, page=2, limit=2))

        assert [t.id for t in page_one] == [threads[0].id, threads[1].id]
        assert [t.id for t in page_two] == [threads[2].id]

    async def test_get_all_orders_by_last_post_at_descending(
        self, repository, create, forum
    ):
        now = datetime.now(timezone.utc)
        # The thread created first has the most recent reply, so it comes first.
        replied_to = await create(
            ThreadFactory,
            forum=forum,
            last_post_at=now,
            created_at=now - timedelta(days=2),
        )
        newer = await create(
            ThreadFactory,
            forum=forum,
            last_post_at=now - timedelta(days=1),
            created_at=now - timedelta(days=1),
        )

        threads = list(await repository.get_all(forum.id))

        assert [t.id for t in threads] == [replied_to.id, newer.id]

    async def test_get_all_breaks_last_post_at_ties_by_id_descending(
        self, repository, create, forum
    ):
        tied_at = datetime.now(timezone.utc)
        first = await create(ThreadFactory, forum=forum, last_post_at=tied_at)
        second = await create(ThreadFactory, forum=forum, last_post_at=tied_at)

        threads = list(await repository.get_all(forum.id))

        assert [t.id for t in threads] == [second.id, first.id]

    async def test_get_all_sorts_sticky_threads_first(self, repository, create, forum):
        now = datetime.now(timezone.utc)
        newer = await create(ThreadFactory, forum=forum, last_post_at=now)
        older_sticky = await create(
            ThreadFactory,
            forum=forum,
            last_post_at=now - timedelta(days=1),
            options=Thread.Options(sticky=True),
        )

        threads = list(await repository.get_all(forum.id))

        assert [t.id for t in threads] == [older_sticky.id, newer.id]

    async def test_get_all_treats_missing_sticky_key_as_not_sticky(
        self, repository, create, forum, db_session
    ):
        now = datetime.now(timezone.utc)
        stale = await create(
            ThreadFactory, forum=forum, last_post_at=now - timedelta(days=1)
        )
        await db_session.execute(
            text("UPDATE threads SET options = '{}' WHERE id = :id"),
            {"id": stale.id},
        )
        newer_sticky = await create(
            ThreadFactory,
            forum=forum,
            last_post_at=now,
            options=Thread.Options(sticky=True),
        )

        threads = list(await repository.get_all(forum.id))

        assert [t.id for t in threads] == [newer_sticky.id, stale.id]

    async def test_count_by_forum(self, repository, create, forum):
        other_forum = await create(ForumFactory, heritage=[])
        await create(ThreadFactory, forum=forum)
        await create(ThreadFactory, forum=forum)
        await create(ThreadFactory, forum=other_forum)

        count = await repository.count_by_forum(forum.id)

        assert count == 2

    async def test_create_creates_thread_for_forum(self, repository, forum):
        thread = await repository.create(forum.id, Thread.Options(sticky=True))

        assert thread.id is not None
        assert thread.forum_id == forum.id
        assert thread.options == Thread.Options(sticky=True)

    async def test_create_increments_forum_thread_count(self, repository, forum):
        await repository.create(forum.id, Thread.Options())
        await repository.create(forum.id, Thread.Options())

        assert forum.thread_count == 2

    async def test_attach_new_post_increments_forum_post_count(
        self, repository, create, forum
    ):
        thread = await repository.create(forum.id, Thread.Options())
        for _ in range(2):
            post = await create(PostFactory, thread=thread)
            await repository.attach_new_post(thread, post)

        assert forum.post_count == 2

    async def test_delete_removes_thread_and_its_posts_from_forum_counts(
        self, repository, create, forum
    ):
        other_thread = await repository.create(forum.id, Thread.Options())
        other_post = await create(PostFactory, thread=other_thread)
        await repository.attach_new_post(other_thread, other_post)
        thread = await repository.create(forum.id, Thread.Options())
        for _ in range(3):
            post = await create(PostFactory, thread=thread)
            await repository.attach_new_post(thread, post)

        await repository.delete(thread)

        assert forum.thread_count == 1
        assert forum.post_count == 1

    async def test_attach_new_post_sets_first_and_last_post(
        self, repository, create, forum
    ):
        thread = await repository.create(forum.id, Thread.Options())
        post = await create(PostFactory, thread=thread)

        await repository.attach_new_post(thread, post)

        assert thread.first_post_id == post.id
        assert thread.last_post_id == post.id
        assert thread.last_post_at == post.published_at
        assert thread.post_count == 1

    async def test_attach_new_post_keeps_first_post_and_updates_last_post(
        self, repository, create, forum
    ):
        thread = await repository.create(forum.id, Thread.Options())
        first_post = await create(PostFactory, thread=thread)
        await repository.attach_new_post(thread, first_post)
        second_post = await create(PostFactory, thread=thread)

        await repository.attach_new_post(thread, second_post)

        assert thread.first_post_id == first_post.id
        assert thread.last_post_id == second_post.id
        assert thread.last_post_at == second_post.published_at
        assert thread.post_count == 2

    async def test_delete_excludes_thread_from_get_all(self, repository, create, forum):
        thread = await create(ThreadFactory, forum=forum)

        await repository.delete(thread)
        threads = list(await repository.get_all(forum.id))

        assert thread.deleted is not None
        assert threads == []

    async def test_detach_post_decrements_post_count(self, repository, create, forum):
        thread = await repository.create(forum.id, Thread.Options())
        first_post = await create(PostFactory, thread=thread)
        await repository.attach_new_post(thread, first_post)
        second_post = await create(PostFactory, thread=thread)
        await repository.attach_new_post(thread, second_post)

        await repository.detach_post(thread, second_post)

        assert thread.post_count == 1
        assert forum.post_count == 1

    async def test_detach_post_updates_last_post_to_previous_post(
        self, repository, create, forum
    ):
        thread = await repository.create(forum.id, Thread.Options())
        first_post = await create(PostFactory, thread=thread)
        await repository.attach_new_post(thread, first_post)
        second_post = await create(PostFactory, thread=thread)
        await repository.attach_new_post(thread, second_post)

        await repository.detach_post(thread, second_post)

        assert thread.last_post_id == first_post.id
        assert thread.last_post_at == first_post.published_at

    async def test_detach_post_leaves_last_post_when_not_last_post(
        self, repository, create, forum
    ):
        thread = await repository.create(forum.id, Thread.Options())
        first_post = await create(PostFactory, thread=thread)
        await repository.attach_new_post(thread, first_post)
        second_post = await create(PostFactory, thread=thread)
        await repository.attach_new_post(thread, second_post)
        third_post = await create(PostFactory, thread=thread)
        await repository.attach_new_post(thread, third_post)

        await repository.detach_post(thread, second_post)

        assert thread.last_post_id == third_post.id
        assert thread.last_post_at == third_post.published_at
        assert thread.post_count == 2

    async def test_get_last_posts_by_forum_ids_across_multiple_threads(
        self, repository, create, forum
    ):
        older_thread = await create(ThreadFactory, forum=forum)
        older_post = await create(
            PostFactory, thread=older_thread, published_at=datetime(2026, 1, 1)
        )
        await repository.attach_new_post(older_thread, older_post)

        newer_thread = await create(ThreadFactory, forum=forum)
        newer_post = await create(
            PostFactory, thread=newer_thread, published_at=datetime(2026, 2, 1)
        )
        await repository.attach_new_post(newer_thread, newer_post)

        last_posts = await repository.get_last_posts_by_forum_ids([forum.id])

        assert last_posts[forum.id].id == newer_post.id

    async def test_get_last_posts_by_forum_ids_excludes_other_forums(
        self, repository, create, forum
    ):
        other_forum = await create(ForumFactory, heritage=[])
        other_thread = await create(ThreadFactory, forum=other_forum)
        other_post = await create(PostFactory, thread=other_thread)
        await repository.attach_new_post(other_thread, other_post)

        last_posts = await repository.get_last_posts_by_forum_ids([forum.id])

        assert forum.id not in last_posts
        assert other_forum.id not in last_posts

    async def test_get_featured_picks_a_sticky_thread(
        self, repository, create, db_session, forum
    ):
        sticky = set()
        for _ in range(2):
            thread = await add_thread(create, db_session, forum)
            thread.options = Thread.Options(sticky=True)
            sticky.add(thread.id)
        await add_thread(create, db_session, forum)
        await db_session.flush()

        # Random, so ask a few times: a plain thread is never chosen.
        for _ in range(6):
            featured = await repository.get_featured(forum.id)
            assert featured.id in sticky

    async def test_get_featured_without_sticky_threads_picks_the_newest(
        self, repository, create, db_session, forum
    ):
        await add_thread(create, db_session, forum, days=2)
        newest = await add_thread(create, db_session, forum, days=1)

        featured = await repository.get_featured(forum.id)

        assert featured.id == newest.id

    async def test_get_featured_skips_threads_without_a_first_post(
        self, repository, create, db_session, forum
    ):
        with_post = await add_thread(create, db_session, forum)
        await create(ThreadFactory, forum=forum)

        featured = await repository.get_featured(forum.id)

        assert featured.id == with_post.id

    async def test_get_featured_is_none_for_a_forum_without_threads(
        self, repository, forum
    ):
        assert await repository.get_featured(forum.id) is None
