from datetime import UTC, datetime, timedelta

import pytest

from app.repositories.thread_repository import ThreadRepository
from tests.factories import ForumFactory, ThreadFactory
from tests.game_forum import make_game_forum

NOW = datetime.now(UTC)
SINCE = NOW - timedelta(days=7)


class TestRecentlyActiveForumIds:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return ThreadRepository(db_session, principal=None)

    async def test_forums_with_a_live_thread_active_since_the_cutoff(
        self, repository, create, wrap_in_savepoint
    ):
        active = await create(ForumFactory, heritage=[])
        stale = await create(ForumFactory, heritage=[])
        deleted_only = await create(ForumFactory, heritage=[])
        no_last_post = await create(ForumFactory, heritage=[])
        deleted_forum = await create(ForumFactory, heritage=[], deleted=NOW)
        await create(ThreadFactory, forum=deleted_forum, last_post_at=NOW)
        await create(ThreadFactory, forum=active, last_post_at=NOW)
        await create(ThreadFactory, forum=active, last_post_at=NOW)
        await create(ThreadFactory, forum=stale, last_post_at=NOW - timedelta(days=8))
        await create(ThreadFactory, forum=deleted_only, last_post_at=NOW, deleted=NOW)
        await create(ThreadFactory, forum=no_last_post)

        assert await repository.recently_active_forum_ids(SINCE) == {active.id}

    async def test_game_only_leaves_out_forums_outside_games(
        self, repository, create, db_session
    ):
        game = await make_game_forum(create, db_session)
        site = await create(ForumFactory, heritage=[])
        await create(ThreadFactory, forum=game.forum, last_post_at=NOW)
        await create(ThreadFactory, forum=site, last_post_at=NOW)

        assert await repository.recently_active_forum_ids(SINCE, game_only=True) == {
            game.forum.id
        }
        assert await repository.recently_active_forum_ids(SINCE) == {
            game.forum.id,
            site.id,
        }
