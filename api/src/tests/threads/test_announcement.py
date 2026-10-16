import pytest
from sqlalchemy import text

from app.models import Post
from app.threads.routes import ANNOUNCEMENTS_FORUM_ID
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import ForumFactory
from tests.threads.test_search_routes import add_thread


@pytest.fixture
async def announcements(create, db_session):
    forum = await create(
        ForumFactory, id=ANNOUNCEMENTS_FORUM_ID, heritage=[SITE_ROOT_FORUM_ID]
    )
    # An explicit id bypasses the forums sequence, so move it past that id.
    await db_session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('forums', 'id'), "
            "(SELECT MAX(id) FROM forums))"
        )
    )
    return forum


# Which thread is chosen is covered by ThreadRepository.get_featured's tests.
class TestGetAnnouncement:
    async def test_shows_the_threads_title_and_first_post(
        self, authed_client, create, db_session, announcements
    ):
        client, _ = authed_client
        thread = await add_thread(create, db_session, announcements)

        response = await client.get("/threads/announcement")

        post = await db_session.get(Post, thread.first_post_id)
        data = response.json()
        assert data["id"] == thread.id
        assert data["title"] == post.title
        assert data["post"]["id"] == post.id
        assert data["post"]["body"] == post.body
        assert data["post"]["author"]["username"]

    async def test_forum_without_threads_is_404(self, authed_client, announcements):
        client, _ = authed_client

        response = await client.get("/threads/announcement")

        assert response.status_code == 404
