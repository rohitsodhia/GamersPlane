import pytest

from app.models import Post
from app.repositories.post_repository import PostRepository
from tests.factories import ThreadFactory, UserFactory, prose_doc


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
            thread.id, author.id, "Hello", prose_doc("Hi there"), state=Post.States.POST
        )

        assert post.state == Post.States.POST
