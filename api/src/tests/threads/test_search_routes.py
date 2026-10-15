from datetime import UTC, datetime, timedelta

import pytest

from app.models import FavoriteGame, RolePermission
from app.repositories import ThreadRepository
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import ForumFactory, PostFactory, ThreadFactory
from tests.game_forum import grant, make_game_forum

Verbs = RolePermission.ValidPermissions


async def add_thread(create, db_session, forum, **ago):
    """A thread in ``forum`` whose only post was published ``ago`` ago (hours by
    default)."""
    thread = await create(ThreadFactory, forum=forum)
    post = await create(
        PostFactory,
        thread=thread,
        published_at=datetime.now(UTC) - timedelta(**(ago or {"hours": 1})),
    )
    await ThreadRepository(db_session, principal=None).attach_new_post(thread, post)
    return thread


async def favorite(db_session, user, *games):
    db_session.add_all(FavoriteGame(user_id=user.id, game_id=g.id) for g in games)
    await db_session.flush()


def ids(response) -> list[int]:
    return [thread["id"] for thread in response.json()["threads"]]


@pytest.fixture
async def open_forum(create):
    return await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])


@pytest.fixture
async def closed_forum(create):
    return await create(ForumFactory, heritage=[])


@pytest.fixture
async def games(create, db_session):
    """A public game and a private one, as ``(public, private)`` forums."""
    public = await make_game_forum(create, db_session)
    private = await public.make_game("Secret Game")
    private.game.public = False
    await db_session.flush()
    return public, private


class TestLatest:
    async def test_lists_readable_threads_from_the_past_week_newest_first(
        self, client, create, db_session, open_forum, closed_forum
    ):
        older = await add_thread(create, db_session, open_forum, days=3)
        newest = await add_thread(create, db_session, open_forum, hours=1)
        await add_thread(create, db_session, open_forum, days=8)
        await add_thread(create, db_session, closed_forum, hours=1)

        response = await client.get("/threads/search", params={"scope": "latest"})

        assert response.status_code == 200
        assert ids(response) == [newest.id, older.id]
        assert response.json()["count"] == 2
        assert response.json()["page"] == 1

    async def test_member_sees_a_forum_they_were_granted_and_guest_does_not(
        self, authed_client, client, create, db_session, closed_forum
    ):
        _, user = authed_client
        await grant(db_session, user, closed_forum, Verbs.FORUM_READ)
        thread = await add_thread(create, db_session, closed_forum)

        member = await client.get("/threads/search", params={"scope": "latest"})
        del client.headers["Authorization"]
        guest = await client.get("/threads/search", params={"scope": "latest"})

        assert ids(member) == [thread.id]
        assert ids(guest) == []

    async def test_threads_say_where_they_are_and_who_posted_last(
        self, client, create, db_session
    ):
        parent = await create(
            ForumFactory, title="Parent", heritage=[SITE_ROOT_FORUM_ID]
        )
        child = await create(
            ForumFactory,
            title="Child",
            parent_id=parent.id,
            heritage=[SITE_ROOT_FORUM_ID, parent.id],
        )
        thread = await add_thread(create, db_session, child)

        response = await client.get("/threads/search", params={"scope": "latest"})

        [listed] = response.json()["threads"]
        assert listed["id"] == thread.id
        assert listed["forum"] == {
            "id": child.id,
            "title": "Child",
            "game_id": None,
            "heritage": [{"id": parent.id, "title": "Parent"}],
        }
        assert listed["last_post"]["id"] == thread.last_post_id
        assert listed["last_post"]["author"]["username"]

    async def test_has_unread_is_per_user_and_false_for_guests(
        self, authed_client, client, create, db_session, open_forum
    ):
        _, _user = authed_client
        unread = await add_thread(create, db_session, open_forum, hours=2)
        read = await add_thread(create, db_session, open_forum, hours=1)
        await client.post(f"/threads/{read.id}/mark-read")

        member = await client.get("/threads/search", params={"scope": "latest"})
        del client.headers["Authorization"]
        guest = await client.get("/threads/search", params={"scope": "latest"})

        flags = {t["id"]: t["has_unread"] for t in member.json()["threads"]}
        assert flags == {unread.id: True, read.id: False}
        assert not any(t["has_unread"] for t in guest.json()["threads"])

    async def test_pages_past_the_end_are_empty_and_below_one_are_page_one(
        self, client, create, db_session, open_forum
    ):
        thread = await add_thread(create, db_session, open_forum)

        past = await client.get(
            "/threads/search", params={"scope": "latest", "page": 2}
        )
        below = await client.get(
            "/threads/search", params={"scope": "latest", "page": 0}
        )

        assert ids(past) == []
        assert past.json()["count"] == 1
        assert past.json()["page"] == 2
        assert ids(below) == [thread.id]
        assert below.json()["page"] == 1


class TestLatestGame:
    async def test_only_game_forums_the_principal_can_read(
        self, authed_client, create, db_session, open_forum, games
    ):
        client, user = authed_client
        public, private = games
        await grant(db_session, user, private.forum, Verbs.FORUM_READ)
        await favorite(db_session, user, public.game, private.game)
        in_public = await add_thread(create, db_session, public.forum)
        in_private = await add_thread(create, db_session, private.forum, hours=2)
        await add_thread(create, db_session, open_forum)

        response = await client.get("/threads/search", params={"scope": "latest_game"})

        assert sorted(ids(response)) == sorted([in_public.id, in_private.id])
        assert response.json()["threads"][0]["forum"]["game_id"] is not None

    async def test_game_forums_the_principal_cannot_read_are_left_out(
        self, authed_client, create, db_session, games
    ):
        client, user = authed_client
        _, private = games
        # Their own game, but they have no read access to it.
        await favorite(db_session, user, private.game)
        await add_thread(create, db_session, private.forum)

        response = await client.get("/threads/search", params={"scope": "latest_game"})

        assert ids(response) == []


class TestLatestPublic:
    async def test_only_game_forums_guests_can_read_even_when_logged_in(
        self, authed_client, create, db_session, open_forum, games
    ):
        client, user = authed_client
        public, private = games
        # Readable by this member, but not by guests: not a public game.
        await grant(db_session, user, private.forum, Verbs.FORUM_READ)
        listed = await add_thread(create, db_session, public.forum)
        await add_thread(create, db_session, private.forum)
        await add_thread(create, db_session, open_forum)

        response = await client.get(
            "/threads/search", params={"scope": "latest_public"}
        )

        assert ids(response) == [listed.id]

    async def test_guests_can_list_them(self, client, create, db_session, games):
        public, _ = games
        listed = await add_thread(create, db_session, public.forum)

        response = await client.get(
            "/threads/search", params={"scope": "latest_public"}
        )

        assert ids(response) == [listed.id]


class TestUnread:
    async def test_guests_need_to_log_in(self, client):
        response = await client.get("/threads/search", params={"scope": "unread"})

        assert response.status_code == 403

    async def test_lists_only_unread_threads_from_the_past_week(
        self, authed_client, create, db_session, open_forum, closed_forum
    ):
        client, _ = authed_client
        unread = await add_thread(create, db_session, open_forum, hours=1)
        read = await add_thread(create, db_session, open_forum, hours=2)
        await add_thread(create, db_session, open_forum, days=8)
        await add_thread(create, db_session, closed_forum)
        await client.post(f"/threads/{read.id}/mark-read")

        response = await client.get("/threads/search", params={"scope": "unread"})

        assert ids(response) == [unread.id]
        assert response.json()["count"] == 1
        assert response.json()["threads"][0]["has_unread"] is True
