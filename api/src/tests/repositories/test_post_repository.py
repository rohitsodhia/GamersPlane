from datetime import datetime, timedelta, timezone

import pytest

from app.models import Game, Post
from app.repositories.post_repository import PostRepository
from tests.factories import (
    ForumFactory,
    PostFactory,
    RoleFactory,
    SystemFactory,
    ThreadFactory,
    UserFactory,
    prose_doc,
)


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

    async def test_get_returns_post_by_id(self, repository, create, thread):
        post = await create(PostFactory, thread=thread)

        found = await repository.get(post.id)

        assert found.id == post.id

    async def test_get_returns_none_when_not_found(self, repository):
        found = await repository.get(999999)

        assert found is None

    async def test_get_returns_none_for_deleted_post(self, repository, create, thread):
        post = await create(PostFactory, thread=thread)

        await repository.delete(post)
        found = await repository.get(post.id)

        assert found is None

    async def test_update_updates_title_and_body(self, repository, create, thread):
        post = await create(PostFactory, thread=thread, title="Old Title")
        new_body = prose_doc("New body")

        updated = await repository.update(post, "New Title", new_body)

        assert updated.title == "New Title"
        assert updated.body == new_body

    async def test_update_persists_changes(
        self, repository, create, thread, db_session
    ):
        post = await create(PostFactory, thread=thread, title="Old Title")
        new_body = prose_doc("New body")

        await repository.update(post, "New Title", new_body)
        await db_session.refresh(post)

        assert post.title == "New Title"
        assert post.body == new_body

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

    async def test_get_page_number_returns_one_for_draft_post(
        self, repository, create, thread
    ):
        post = await create(PostFactory, thread=thread, state=Post.States.DRAFT)

        page = await repository.get_page_number(post)

        assert page == 1

    async def test_get_page_number_returns_one_for_first_post(
        self, repository, create, thread
    ):
        post = await create(PostFactory, thread=thread)

        page = await repository.get_page_number(post)

        assert page == 1

    async def test_get_page_number_returns_one_when_within_first_page(
        self, repository, create, thread
    ):
        now = datetime.now(timezone.utc)
        await create(PostFactory, thread=thread, published_at=now - timedelta(days=1))
        post = await create(PostFactory, thread=thread, published_at=now)

        page = await repository.get_page_number(post, limit=2)

        assert page == 1

    async def test_get_page_number_returns_second_page_when_limit_exceeded(
        self, repository, create, thread
    ):
        now = datetime.now(timezone.utc)
        for i in range(2):
            await create(
                PostFactory, thread=thread, published_at=now - timedelta(days=2 - i)
            )
        post = await create(PostFactory, thread=thread, published_at=now)

        page = await repository.get_page_number(post, limit=2)

        assert page == 2

    async def test_get_page_number_ignores_other_threads(
        self, repository, create, thread
    ):
        other_thread = await create(ThreadFactory)
        await create(PostFactory, thread=other_thread)
        post = await create(PostFactory, thread=thread)

        page = await repository.get_page_number(post, limit=2)

        assert page == 1

    async def test_delete_sets_deleted_timestamp(self, repository, create, thread):
        post = await create(PostFactory, thread=thread)

        await repository.delete(post)

        assert post.deleted is not None

    async def test_delete_excludes_post_from_get_all(self, repository, create, thread):
        post = await create(PostFactory, thread=thread)

        await repository.delete(post)
        posts = list(await repository.get_all(thread.id))

        assert posts == []

    async def test_delete_excludes_post_from_count_by_thread(
        self, repository, create, thread
    ):
        post = await create(PostFactory, thread=thread)

        await repository.delete(post)
        count = await repository.count_by_thread(thread.id)

        assert count == 0

    async def test_get_page_number_ignores_draft_posts_before_it(
        self, repository, create, thread
    ):
        now = datetime.now(timezone.utc)
        await create(
            PostFactory,
            thread=thread,
            state=Post.States.DRAFT,
            published_at=now - timedelta(days=1),
        )
        post = await create(PostFactory, thread=thread, published_at=now)

        page = await repository.get_page_number(post, limit=1)

        assert page == 1


class TestCountByAuthor:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return PostRepository(db_session, auth=[])

    @pytest.fixture
    async def author(self, create, wrap_in_savepoint):
        return await create(UserFactory)

    @pytest.fixture
    async def community_thread(self, create, wrap_in_savepoint):
        return await create(ThreadFactory)

    @pytest.fixture
    async def game_forum(self, db_session, create, wrap_in_savepoint):
        system = await create(SystemFactory)
        gm = await create(UserFactory)
        role = await create(RoleFactory)
        root_forum = await create(ForumFactory)
        game = Game(
            title="Test Game",
            system=system,
            gm=gm,
            post_frequency="1d",
            num_players=4,
            root_forum=root_forum,
            role=role,
            public=True,
        )
        db_session.add(game)
        await db_session.flush()

        return await create(ForumFactory, game_id=game.id)

    @pytest.fixture
    async def game_thread(self, create, game_forum, wrap_in_savepoint):
        return await create(ThreadFactory, forum=game_forum)

    async def test_counts_community_post(
        self, repository, create, author, community_thread
    ):
        await create(PostFactory, thread=community_thread, author=author)

        game_count, community_count = await repository.count_by_author(author.id)

        assert (game_count, community_count) == (0, 1)

    async def test_counts_game_post(self, repository, create, author, game_thread):
        await create(PostFactory, thread=game_thread, author=author)

        game_count, community_count = await repository.count_by_author(author.id)

        assert (game_count, community_count) == (1, 0)

    async def test_counts_mixed_posts(
        self, repository, create, author, community_thread, game_thread
    ):
        await create(PostFactory, thread=community_thread, author=author)
        await create(PostFactory, thread=community_thread, author=author)
        await create(PostFactory, thread=game_thread, author=author)

        game_count, community_count = await repository.count_by_author(author.id)

        assert (game_count, community_count) == (1, 2)

    async def test_excludes_other_authors(
        self, repository, create, author, community_thread
    ):
        other = await create(UserFactory)
        await create(PostFactory, thread=community_thread, author=other)

        game_count, community_count = await repository.count_by_author(author.id)

        assert (game_count, community_count) == (0, 0)

    async def test_excludes_non_published_posts(
        self, repository, create, author, community_thread
    ):
        await create(
            PostFactory,
            thread=community_thread,
            author=author,
            state=Post.States.DRAFT,
        )
        await create(
            PostFactory,
            thread=community_thread,
            author=author,
            state=Post.States.REVISED,
        )

        game_count, community_count = await repository.count_by_author(author.id)

        assert (game_count, community_count) == (0, 0)

    async def test_excludes_deleted_posts(
        self, repository, create, author, community_thread
    ):
        post = await create(PostFactory, thread=community_thread, author=author)

        await repository.delete(post)
        game_count, community_count = await repository.count_by_author(author.id)

        assert (game_count, community_count) == (0, 0)

    async def test_zero_when_no_posts(self, repository, author):
        game_count, community_count = await repository.count_by_author(author.id)

        assert (game_count, community_count) == (0, 0)
