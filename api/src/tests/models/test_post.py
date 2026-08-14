from datetime import UTC, datetime

from app.models import Post
from tests.factories import PostFactory


class TestPublishedAt:
    async def test_publishing_sets_published_at(self, create, wrap_in_savepoint):
        post = await create(PostFactory, state=Post.States.DRAFT)

        post.state = Post.States.PUBLISHED

        assert post.published_at is not None

    async def test_creating_as_published_sets_published_at(
        self, create, wrap_in_savepoint
    ):
        post = await create(PostFactory, state=Post.States.PUBLISHED)

        assert post.published_at is not None

    async def test_creating_as_draft_leaves_published_at_unset(
        self, create, wrap_in_savepoint
    ):
        post = await create(PostFactory, state=Post.States.DRAFT)

        assert post.published_at is None

    async def test_republishing_does_not_change_existing_published_at(
        self, create, wrap_in_savepoint
    ):
        original = datetime(2026, 1, 1, tzinfo=UTC)
        post = await create(
            PostFactory, state=Post.States.PUBLISHED, published_at=original
        )

        post.state = Post.States.REVISED
        post.state = Post.States.PUBLISHED

        assert post.published_at == original
