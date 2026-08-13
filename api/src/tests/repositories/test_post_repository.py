from datetime import datetime, timedelta, timezone

import pytest

from app.models import Post
from app.repositories.post_repository import PostRepository
from tests.factories import PostFactory, ThreadFactory, UserFactory, prose_doc


class TestPostRepository:
    @pytest.fixture
    async def thread(self, create, wrap_in_savepoint):
        return await create(ThreadFactory)

    @pytest.fixture
    async def author(self, create, wrap_in_savepoint):
        return await create(UserFactory)

    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return PostRepository(db_session, auth=[])

    async def test_create_creates_post(self, repository, thread, author):
        body = prose_doc("Hi there")

        post = await repository.create(thread.id, author.id, "Hello", body)

        assert post.id is not None
        assert post.thread_id == thread.id
        assert post.author_id == author.id
        assert post.title == "Hello"
        assert post.body == body

    async def test_create_defaults_to_draft_state(self, repository, thread, author):
        post = await repository.create(
            thread.id, author.id, "Hello", prose_doc("Hi there")
        )

        assert post.state == Post.States.DRAFT

    async def test_create_accepts_explicit_state(self, repository, thread, author):
        post = await repository.create(
            thread.id,
            author.id,
            "Hello",
            prose_doc("Hi there"),
            state=Post.States.PUBLISHED,
        )

        assert post.state == Post.States.PUBLISHED

    async def test_get_all_returns_published_posts_for_thread(
        self, repository, create, thread
    ):
        post = await create(PostFactory, thread=thread)

        posts = list(await repository.get_all(thread.id))

        assert [p.id for p in posts] == [post.id]

    async def test_get_all_excludes_other_threads(self, repository, create, thread):
        other_thread = await create(ThreadFactory)
        await create(PostFactory, thread=other_thread)

        posts = list(await repository.get_all(thread.id))

        assert posts == []

    async def test_get_all_excludes_draft_posts(self, repository, create, thread):
        await create(PostFactory, thread=thread, state=Post.States.DRAFT)

        posts = list(await repository.get_all(thread.id))

        assert posts == []

    async def test_get_all_excludes_revised_posts(self, repository, create, thread):
        await create(PostFactory, thread=thread, state=Post.States.REVISED)

        posts = list(await repository.get_all(thread.id))

        assert posts == []

    async def test_get_all_orders_by_published_at_ascending(
        self, repository, create, thread
    ):
        now = datetime.now(timezone.utc)
        newer = await create(
            PostFactory, thread=thread, published_at=now, title="Newer"
        )
        older = await create(
            PostFactory,
            thread=thread,
            published_at=now - timedelta(days=1),
            title="Older",
        )

        posts = list(await repository.get_all(thread.id))

        assert [p.id for p in posts] == [older.id, newer.id]

    async def test_get_all_respects_limit(self, repository, create, thread):
        for _ in range(3):
            await create(PostFactory, thread=thread)

        posts = list(await repository.get_all(thread.id, page=1, limit=2))

        assert len(posts) == 2

    async def test_get_all_paginates_to_second_page(self, repository, create, thread):
        posts_created = [await create(PostFactory, thread=thread) for _ in range(3)]

        page_two = list(await repository.get_all(thread.id, page=2, limit=2))

        assert [p.id for p in page_two] == [posts_created[2].id]

    async def test_count_by_thread(self, repository, create, thread):
        await create(PostFactory, thread=thread)
        await create(PostFactory, thread=thread)

        count = await repository.count_by_thread(thread.id)

        assert count == 2

    async def test_count_by_thread_excludes_other_threads(
        self, repository, create, thread
    ):
        other_thread = await create(ThreadFactory)
        await create(PostFactory, thread=thread)
        await create(PostFactory, thread=other_thread)

        count = await repository.count_by_thread(thread.id)

        assert count == 1

    async def test_count_by_thread_excludes_non_published_posts(
        self, repository, create, thread
    ):
        await create(PostFactory, thread=thread, state=Post.States.DRAFT)
        await create(PostFactory, thread=thread, state=Post.States.REVISED)
        await create(PostFactory, thread=thread)

        count = await repository.count_by_thread(thread.id)

        assert count == 1

    async def test_count_by_thread_zero_when_no_posts(self, repository, thread):
        count = await repository.count_by_thread(thread.id)

        assert count == 0
