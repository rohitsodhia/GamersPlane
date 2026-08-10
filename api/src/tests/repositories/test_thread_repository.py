import pytest

from app.repositories.thread_repository import ThreadRepository
from tests.factories import ForumFactory, ThreadFactory


class TestThreadRepository:
    @pytest.fixture
    async def forum(self, create, wrap_in_savepoint):
        return await create(ForumFactory, heritage=[])

    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return ThreadRepository(db_session, auth=[])

    async def test_get_all_returns_threads_for_forum(
        self, repository, create, forum
    ):
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
