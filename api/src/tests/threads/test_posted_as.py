import pytest

from app.configs import configs
from app.models import Post, Thread
from tests.factories import prose_doc
from tests.game_forum import (
    PLAYER_VERBS,
    add_avatar,
    make_character,
    make_game_forum,
    make_user_with,
)

WEBHOOK_URL = "https://discord.com/api/webhooks/123456789/abc-DEF_123"


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
    async def test_own_character_is_stored_on_the_first_post(
        self, auth_as, db_session, world, player
    ):
        character = await make_character(db_session, player, world.game)
        client = auth_as(player)

        response = await client.post(
            "/threads", json=new_thread(world.forum, posted_as_id=character.id)
        )

        assert response.status_code == 200
        thread = await db_session.get(Thread, response.json()["id"])
        post = await db_session.get(Post, thread.first_post_id)
        assert post.posted_as_id == character.id

    async def test_another_players_character_is_rejected(
        self, auth_as, create, db_session, world, player
    ):
        other = await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)
        character = await make_character(db_session, other, world.game)
        client = auth_as(player)

        response = await client.post(
            "/threads", json=new_thread(world.forum, posted_as_id=character.id)
        )

        assert response.status_code == 400

    async def test_webhook_goes_out_under_the_characters_name(
        self, auth_as, db_session, world, player, sent_webhooks
    ):
        character = await make_character(db_session, player, world.game, name="Aria")
        avatar_id = await add_avatar(db_session, character)
        # The GM may set a webhook and post as the player's character.
        client = auth_as(world.gm)
        response = await client.post(
            "/threads",
            json=new_thread(
                world.forum,
                posted_as_id=character.id,
                options={"discord_webhook": WEBHOOK_URL},
            ),
        )

        assert response.status_code == 200
        [(_url, payload)] = sent_webhooks
        assert payload["username"] == "Aria"
        assert (
            payload["avatar_url"]
            == f"{configs.AVATARS_ROOT}/characters/{avatar_id}.png"
        )
