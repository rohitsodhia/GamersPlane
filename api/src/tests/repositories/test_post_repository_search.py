from datetime import UTC, datetime, timedelta

import pytest

from app.models import Post
from app.repositories.post_repository import (
    SNIPPET_MATCH_END,
    SNIPPET_MATCH_START,
    PostRepository,
)
from tests.factories import ForumFactory, PostFactory, ThreadFactory

NOW = datetime.now(UTC)


class TestSearch:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return PostRepository(db_session, principal=None)

    @pytest.fixture
    async def forum(self, create, wrap_in_savepoint):
        return await create(ForumFactory, heritage=[])

    @pytest.fixture
    def make_post(self, create, forum):
        async def _make_post(title="Untitled", body_text="", **kwargs):
            thread = kwargs.pop("thread", None) or await create(
                ThreadFactory, forum=forum
            )
            return await create(
                PostFactory,
                thread=thread,
                title=title,
                body_text=body_text,
                published_at=kwargs.pop("published_at", NOW),
                **kwargs,
            )

        return _make_post

    async def ids(self, repository, text, forum_ids, **kwargs) -> list[int]:
        results, _, _ = await repository.search(text, forum_ids, **kwargs)
        return [result.post_id for result in results]

    async def test_matches_title_and_body_with_stemming(
        self, repository, forum, make_post
    ):
        in_title = await make_post(title="Goblin ambush")
        in_body = await make_post(body_text="The goblins attacked at dawn")
        await make_post(body_text="A quiet tavern")

        ids = await self.ids(repository, "goblin", [forum.id])

        assert sorted(ids) == sorted([in_title.id, in_body.id])

    async def test_title_match_outranks_body_match(self, repository, forum, make_post):
        body_only = await make_post(body_text="goblin", published_at=NOW)
        title = await make_post(title="goblin", published_at=NOW - timedelta(days=5))

        assert await self.ids(repository, "goblin", [forum.id]) == [
            title.id,
            body_only.id,
        ]

    async def test_equal_rank_orders_newest_first_then_highest_id(
        self, repository, forum, make_post
    ):
        older = await make_post(
            body_text="goblin", published_at=NOW - timedelta(days=1)
        )
        first = await make_post(body_text="goblin", published_at=NOW)
        second = await make_post(body_text="goblin", published_at=NOW)

        assert await self.ids(repository, "goblin", [forum.id]) == [
            second.id,
            first.id,
            older.id,
        ]

    async def test_drafts_and_deleted_posts_are_left_out(
        self, repository, forum, make_post
    ):
        kept = await make_post(body_text="goblin")
        await make_post(body_text="goblin", state=Post.States.DRAFT)
        await make_post(body_text="goblin", deleted=NOW)

        assert await self.ids(repository, "goblin", [forum.id]) == [kept.id]

    async def test_posts_in_deleted_threads_are_left_out(
        self, repository, forum, create, make_post
    ):
        dead = await create(ThreadFactory, forum=forum, deleted=NOW)
        await make_post(body_text="goblin", thread=dead)

        assert await self.ids(repository, "goblin", [forum.id]) == []

    async def test_only_given_forums(self, repository, create, forum, make_post):
        other = await create(ForumFactory, heritage=[])
        here = await make_post(body_text="goblin")
        await make_post(
            body_text="goblin", thread=await create(ThreadFactory, forum=other)
        )

        assert await self.ids(repository, "goblin", [forum.id]) == [here.id]

    async def test_no_forums_returns_nothing(self, repository, make_post):
        await make_post(body_text="goblin")

        assert await repository.search("goblin", []) == ([], 0, False)

    async def test_pages_report_the_full_count(self, repository, forum, make_post):
        posts = [
            await make_post(body_text="goblin", published_at=NOW - timedelta(days=day))
            for day in range(3)
        ]

        results, count, capped = await repository.search(
            "goblin", [forum.id], page=2, limit=2
        )

        assert [r.post_id for r in results] == [posts[2].id]
        assert count == 3
        assert not capped

    async def test_count_stops_at_the_cap_and_says_so(
        self, repository, forum, make_post, monkeypatch
    ):
        monkeypatch.setattr("app.repositories.post_repository.SEARCH_COUNT_CAP", 2)
        for _ in range(3):
            await make_post(body_text="goblin")

        results, count, capped = await repository.search("goblin", [forum.id])

        assert len(results) == 3
        assert count == 2
        assert capped

    async def test_count_exactly_at_the_cap_is_not_capped(
        self, repository, forum, make_post, monkeypatch
    ):
        monkeypatch.setattr("app.repositories.post_repository.SEARCH_COUNT_CAP", 2)
        for _ in range(2):
            await make_post(body_text="goblin")

        _, count, capped = await repository.search("goblin", [forum.id])

        assert count == 2
        assert not capped

    async def test_search_forum_ids_are_the_forums_with_a_live_match(
        self, repository, create, forum, make_post
    ):
        other = await create(ForumFactory, heritage=[])
        empty = await create(ForumFactory, heritage=[])
        await make_post(body_text="goblin")
        await make_post(
            body_text="goblin", thread=await create(ThreadFactory, forum=other)
        )
        await make_post(
            body_text="goblin",
            state=Post.States.DRAFT,
            thread=await create(ThreadFactory, forum=empty),
        )

        assert await repository.search_forum_ids("goblin") == {forum.id, other.id}

    async def test_websearch_syntax_and_stopword_only_queries_do_not_raise(
        self, repository, forum, make_post
    ):
        await make_post(body_text="goblin chief")

        assert await self.ids(repository, '"goblin chief" -dragon', [forum.id])
        assert await self.ids(repository, "the", [forum.id]) == []

    async def test_result_carries_post_thread_forum_and_author(
        self, repository, forum, make_post
    ):
        post = await make_post(title="Ambush", body_text="goblin")

        [result], _, _ = await repository.search("goblin", [forum.id])

        assert result.post_id == post.id
        assert result.thread_id == post.thread_id
        assert result.title == "Ambush"
        assert result.forum_id == forum.id
        assert result.forum_title == forum.title
        assert result.author_username == post.author.username
        assert result.game_id is None

    async def test_snippet_marks_matches_with_markers_not_markup(
        self, repository, forum, make_post
    ):
        await make_post(body_text="The goblins attacked at dawn")

        [result], _, _ = await repository.search("goblin", [forum.id])

        assert f"{SNIPPET_MATCH_START}goblins{SNIPPET_MATCH_END}" in result.snippet
        # No HTML highlight tags (Postgres's default would be <b>).
        assert "<b>" not in result.snippet
