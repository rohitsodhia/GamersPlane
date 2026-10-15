import pytest
from sqlalchemy import func, select

from app.models import Post
from app.repositories.post_repository import PostRepository
from tests.factories import ThreadFactory, UserFactory


def doc(*paragraphs: str, quote: str | None = None) -> dict:
    content = [
        {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        for text in paragraphs
    ]
    if quote:
        content.append(
            {
                "type": "quote",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": quote}]}
                ],
            }
        )
    return {"type": "doc", "content": content}


class TestPostSearchText:
    @pytest.fixture
    async def repository(self, db_session, wrap_in_savepoint):
        return PostRepository(db_session, principal=None)

    async def matching_ids(self, db_session, query: str) -> list[int]:
        return list(
            await db_session.scalars(
                select(Post.id).where(
                    Post.search_tsv.op("@@")(
                        func.websearch_to_tsquery("english", query)
                    )
                )
            )
        )

    async def test_create_stores_visible_text_of_body(self, repository, create):
        thread = await create(ThreadFactory)
        author = await create(UserFactory)

        post = await repository.create(
            thread.id,
            author.id,
            "Title",
            doc("The goblins", "attack at dawn", quote="someone else's words"),
        )

        assert post.body_text == "The goblins attack at dawn"

    async def test_update_refreshes_body_text(self, repository, create):
        thread = await create(ThreadFactory)
        author = await create(UserFactory)
        post = await repository.create(thread.id, author.id, "Title", doc("Old text"))

        await repository.update(post, "Title", doc("New text"))

        assert post.body_text == "New text"

    async def test_tsvector_matches_stemmed_words(self, repository, create, db_session):
        thread = await create(ThreadFactory)
        author = await create(UserFactory)
        post = await repository.create(
            thread.id, author.id, "Title", doc("The goblins were running")
        )
        # A non-matching post, so the query has to filter.
        await repository.create(thread.id, author.id, "Title", doc("A quiet tavern"))

        ids = await self.matching_ids(db_session, "goblin run")

        assert ids == [post.id]

    async def test_tsvector_matches_title_and_follows_title_update(
        self, repository, create, db_session
    ):
        thread = await create(ThreadFactory)
        author = await create(UserFactory)
        post = await repository.create(
            thread.id, author.id, "Ambush at the bridge", doc("Nothing relevant")
        )

        assert await self.matching_ids(db_session, "ambush") == [post.id]

        await repository.update(post, "Parley at the bridge", doc("Nothing relevant"))

        assert await self.matching_ids(db_session, "ambush") == []
        assert await self.matching_ids(db_session, "parley") == [post.id]

    async def test_tsvector_follows_updated_body(self, repository, create, db_session):
        thread = await create(ThreadFactory)
        author = await create(UserFactory)
        post = await repository.create(thread.id, author.id, "Title", doc("dragons"))

        await repository.update(post, "Title", doc("goblins"))

        assert await self.matching_ids(db_session, "dragon") == []
        assert await self.matching_ids(db_session, "goblin") == [post.id]
