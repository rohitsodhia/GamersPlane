from datetime import UTC, datetime

import pytest

from app.models import RolePermission
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import ForumFactory, PostFactory, ThreadFactory
from tests.game_forum import grant, make_game_forum

Verbs = RolePermission.ValidPermissions


@pytest.fixture(autouse=True)
async def _open_site_root(wrap_in_savepoint, open_forums):
    await open_forums(SITE_ROOT_FORUM_ID)


@pytest.fixture
async def open_forum(create):
    return await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])


@pytest.fixture
def add_post(create):
    async def _add_post(forum, title="Untitled", body_text="", **kwargs):
        thread = await create(ThreadFactory, forum=forum)
        return await create(
            PostFactory,
            thread=thread,
            title=title,
            body_text=body_text,
            published_at=datetime.now(UTC),
            **kwargs,
        )

    return _add_post


def post_ids(response) -> list[int]:
    return [result["post_id"] for result in response.json()["results"]]


class TestSearchPosts:
    async def test_finds_posts_by_text_and_says_where_they_are(
        self, client, open_forum, add_post
    ):
        by_text = await add_post(open_forum, body_text="The goblins attacked at dawn")
        await add_post(open_forum, body_text="A quiet tavern")

        response = await client.get("/forums/search", params={"q": "goblin"})

        assert response.status_code == 200
        body = response.json()
        assert post_ids(response) == [by_text.id]
        assert body["count"] == 1
        assert body["count_capped"] is False
        assert body["page"] == 1
        [result] = body["results"]
        assert result["thread_id"] == by_text.thread_id
        assert result["forum_id"] == open_forum.id
        assert result["forum_title"] == open_forum.title
        assert result["author"] == {
            "id": by_text.author.id,
            "username": by_text.author.username,
        }
        assert result["published_at"]
        assert result["rank"] > 0

    async def test_snippet_is_plain_text_parts_with_matches_flagged(
        self, client, open_forum, add_post
    ):
        await add_post(open_forum, body_text="The goblins attacked at dawn")

        response = await client.get("/forums/search", params={"q": "goblin"})

        parts = response.json()["results"][0]["snippet"]
        assert [p["text"] for p in parts if p["match"]] == ["goblins"]
        # Postgres may trim leading stopwords from a snippet.
        assert "".join(p["text"] for p in parts).endswith("goblins attacked at dawn")

    async def test_guests_search_what_they_can_read_and_members_what_they_were_granted(
        self, authed_client, client, create, db_session, add_post
    ):
        _, user = authed_client
        closed = await create(ForumFactory, heritage=[])
        hidden = await add_post(closed, body_text="goblin")
        await grant(db_session, user, closed, Verbs.FORUM_READ)

        member = await client.get("/forums/search", params={"q": "goblin"})
        del client.headers["Authorization"]
        guest = await client.get("/forums/search", params={"q": "goblin"})

        assert post_ids(member) == [hidden.id]
        assert post_ids(guest) == []

    async def test_game_id_limits_results_to_that_games_forums(
        self, client, create, db_session, open_forum, add_post
    ):
        first = await make_game_forum(create, db_session)
        second = await first.make_game("Other Game")
        in_first = await add_post(first.forum, body_text="goblin")
        await add_post(second.forum, body_text="goblin")
        await add_post(open_forum, body_text="goblin")

        scoped = await client.get(
            "/forums/search", params={"q": "goblin", "game_id": first.game.id}
        )
        everywhere = await client.get("/forums/search", params={"q": "goblin"})

        assert post_ids(scoped) == [in_first.id]
        assert len(post_ids(everywhere)) == 3

    @pytest.mark.parametrize("q", ["", "   ", "x" * 201])
    async def test_blank_or_overlong_query_returns_422(self, client, q):
        response = await client.get("/forums/search", params={"q": q})

        assert response.status_code == 422
