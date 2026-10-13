import pytest

from app.models import Post, Thread
from tests.factories import prose_doc
from tests.game_forum import (
    PLAYER_VERBS,
    add_avatar,
    make_character,
    make_game_forum,
    make_user_with,
)


@pytest.fixture
async def world(create, db_session):
    return await make_game_forum(create, db_session)


@pytest.fixture
async def player(create, db_session, world):
    return await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)


def new_thread(forum, **overrides):
    return {
        "forum_id": forum.id,
        "title": "Hello",
        "body": prose_doc("Hi there"),
        **overrides,
    }


class TestCreateThreadAs:
    async def test_own_character_and_chosen_avatar_are_stored_on_the_first_post(
        self, auth_as, db_session, world, player
    ):
        character = await make_character(db_session, player, world.game)
        await add_avatar(db_session, character)
        second_id = await add_avatar(db_session, character, "jpg")
        client = auth_as(player)

        response = await client.post(
            "/threads",
            json=new_thread(
                world.forum, posted_as_id=character.id, posted_avatar_id=second_id
            ),
        )

        assert response.status_code == 200
        thread = await db_session.get(Thread, response.json()["id"])
        post = await db_session.get(Post, thread.first_post_id)
        assert post.posted_as_id == character.id
        assert post.posted_avatar_id == second_id
