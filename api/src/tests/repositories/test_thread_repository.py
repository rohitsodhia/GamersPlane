from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.models import Post, Thread
from app.repositories.thread_repository import ThreadRepository
from tests.factories import ForumFactory, PostFactory, ThreadFactory


class TestThreadRepository:
    @pytest.fixture
    async def forum(self, create, wrap_in_savepoint):
        return await create(ForumFactory, heritage=[])

    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return ThreadRepository(db_session, auth=[])

    async def test_get_all_returns_threads_for_forum(self, repository, create, forum):
        thread = await create(ThreadFactory, forum=forum)

        threads = list(await repository.get_all(forum.id))

        assert [t.id for t in threads] == [thread.id]

    async def test_get_all_excludes_other_forums(self, repository, create, forum):
        other_forum = await create(ForumFactory, heritage=[])
        await create(ThreadFactory, forum=other_forum)

        threads = list(await repository.get_all(forum.id))

        assert threads == []

    async def test_get_all_respects_limit(self, repository, create, forum):
        for _ in range(3):
            await create(ThreadFactory, forum=forum)

        threads = list(await repository.get_all(forum.id, page=1, limit=2))

        assert len(threads) == 2

    async def test_get_all_paginates_to_second_page(self, repository, create, forum):
        threads = [await create(ThreadFactory, forum=forum) for _ in range(3)]

        page_two = list(await repository.get_all(forum.id, page=2, limit=2))

        assert [t.id for t in page_two] == [threads[2].id]

    async def test_get_all_orders_by_created_at_descending(
        self, repository, create, forum
    ):
        now = datetime.now(timezone.utc)
        older = await create(
            ThreadFactory, forum=forum, created_at=now - timedelta(days=1)
        )
        newer = await create(ThreadFactory, forum=forum, created_at=now)

        threads = list(await repository.get_all(forum.id))

        assert [t.id for t in threads] == [newer.id, older.id]

    async def test_get_all_sorts_sticky_threads_first(self, repository, create, forum):
        now = datetime.now(timezone.utc)
        newer = await create(ThreadFactory, forum=forum, created_at=now)
        older_sticky = await create(
            ThreadFactory,
            forum=forum,
            created_at=now - timedelta(days=1),
            options=Thread.Options(sticky=True),
        )

        threads = list(await repository.get_all(forum.id))

        assert [t.id for t in threads] == [older_sticky.id, newer.id]

    async def test_get_all_treats_missing_sticky_key_as_not_sticky(
        self, repository, create, forum, db_session
    ):
        now = datetime.now(timezone.utc)
        stale = await create(
            ThreadFactory, forum=forum, created_at=now - timedelta(days=1)
        )
        await db_session.execute(
            text("UPDATE threads SET options = '{}' WHERE id = :id"),
            {"id": stale.id},
        )
        newer_sticky = await create(
            ThreadFactory,
            forum=forum,
            created_at=now,
            options=Thread.Options(sticky=True),
        )

        threads = list(await repository.get_all(forum.id))

        assert [t.id for t in threads] == [newer_sticky.id, stale.id]

    async def test_count_by_forum(self, repository, create, forum):
        await create(ThreadFactory, forum=forum)
        await create(ThreadFactory, forum=forum)

        count = await repository.count_by_forum(forum.id)

        assert count == 2

    async def test_count_by_forum_excludes_other_forums(
        self, repository, create, forum
    ):
        other_forum = await create(ForumFactory, heritage=[])
        await create(ThreadFactory, forum=forum)
        await create(ThreadFactory, forum=other_forum)

        count = await repository.count_by_forum(forum.id)

        assert count == 1

    async def test_count_by_forum_zero_when_no_threads(self, repository, forum):
        count = await repository.count_by_forum(forum.id)

        assert count == 0

    async def test_create_creates_thread_for_forum(self, repository, forum):
        thread = await repository.create(forum.id, Thread.Options())

        assert thread.id is not None
        assert thread.forum_id == forum.id

    async def test_create_sets_options(self, repository, forum):
        thread = await repository.create(forum.id, Thread.Options(sticky=True))

        assert thread.options == Thread.Options(sticky=True)

    async def test_attach_new_post_sets_first_and_last_post(
        self, repository, create, forum
    ):
        thread = await repository.create(forum.id, Thread.Options())
        post = await create(PostFactory, thread=thread)

        await repository.attach_new_post(thread, post)

        assert thread.first_post_id == post.id
        assert thread.last_post_id == post.id
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
        assert thread.post_count == 2

    async def test_attach_new_post_rejects_unpublished_post(
        self, repository, create, forum
    ):
        thread = await repository.create(forum.id, Thread.Options())
        draft_post = await create(PostFactory, thread=thread, state=Post.States.DRAFT)

        with pytest.raises(AssertionError):
            await repository.attach_new_post(thread, draft_post)

    async def test_get_last_posts_by_forum_ids_returns_latest_post_per_forum(
        self, repository, create, forum
    ):
        thread = await create(ThreadFactory, forum=forum)
        older_post = await create(PostFactory, thread=thread)
        await repository.attach_new_post(thread, older_post)
        newer_post = await create(PostFactory, thread=thread)
        await repository.attach_new_post(thread, newer_post)

        last_posts = await repository.get_last_posts_by_forum_ids([forum.id])

        assert last_posts[forum.id].id == newer_post.id

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

    async def test_get_last_posts_by_forum_ids_omits_forums_without_posts(
        self, repository, forum
    ):
        last_posts = await repository.get_last_posts_by_forum_ids([forum.id])

        assert last_posts == {}
