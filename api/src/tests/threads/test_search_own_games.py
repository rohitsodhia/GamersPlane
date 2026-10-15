"""Game threads in the listings: only the principal's own games, except for the
public scope."""

import pytest

from app.models import Player
from app.repositories import PlayerRepository
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import ForumFactory
from tests.game_forum import make_game_forum
from tests.threads.test_search_routes import add_thread, favorite, ids


async def listed(client, scope):
    return ids(await client.get("/threads/search", params={"scope": scope}))


@pytest.fixture
async def public_game(create, db_session):
    return await make_game_forum(create, db_session)


@pytest.fixture
async def site_thread(create, db_session):
    forum = await create(ForumFactory, heritage=[SITE_ROOT_FORUM_ID])
    return await add_thread(create, db_session, forum)


class TestOtherPeoplesPublicGames:
    async def test_member_in_no_games_only_sees_them_in_the_public_scope(
        self, authed_client, create, db_session, public_game, site_thread
    ):
        client, _ = authed_client
        game_thread = await add_thread(create, db_session, public_game.forum)

        assert await listed(client, "latest") == [site_thread.id]
        assert await listed(client, "latest_game") == []
        assert await listed(client, "unread") == [site_thread.id]
        assert await listed(client, "latest_public") == [game_thread.id]

    async def test_guest_sees_no_game_threads_in_latest(
        self, client, create, db_session, public_game, site_thread
    ):
        await add_thread(create, db_session, public_game.forum)

        assert await listed(client, "latest") == [site_thread.id]
        assert await listed(client, "latest_game") == []

    async def test_accepted_player_sees_their_games_threads(
        self, authed_client, create, db_session, public_game, site_thread
    ):
        client, user = authed_client
        game_thread = await add_thread(create, db_session, public_game.forum, hours=2)
        await PlayerRepository(db_session, principal=user).attach_player_to_game(
            public_game.game.id, user.id, is_gm=False, state=Player.States.ACCEPTED
        )

        assert await listed(client, "latest") == [site_thread.id, game_thread.id]
        assert await listed(client, "latest_game") == [game_thread.id]
        assert await listed(client, "unread") == [site_thread.id, game_thread.id]

    async def test_only_the_users_own_games_among_several(
        self, authed_client, create, db_session, public_game
    ):
        client, user = authed_client
        other_game = await public_game.make_game("Someone Else's Game")
        mine = await add_thread(create, db_session, public_game.forum)
        await add_thread(create, db_session, other_game.forum)
        await favorite(db_session, user, public_game.game)

        assert await listed(client, "latest") == [mine.id]
        assert await listed(client, "latest_game") == [mine.id]

    async def test_favoriting_a_game_brings_its_threads_in(
        self, authed_client, create, db_session, public_game
    ):
        client, user = authed_client
        game_thread = await add_thread(create, db_session, public_game.forum)
        await favorite(db_session, user, public_game.game)

        assert await listed(client, "latest") == [game_thread.id]
        assert await listed(client, "latest_game") == [game_thread.id]
