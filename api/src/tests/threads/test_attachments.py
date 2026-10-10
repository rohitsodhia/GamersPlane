import pytest
from sqlalchemy import func, select

from app.models import PostDraw, PostRoll, Thread
from tests.factories import prose_doc
from tests.game_forum import (
    PLAYER_VERBS,
    allow_drawing,
    make_game_forum,
    make_user_with,
)


@pytest.fixture
async def world(create, db_session):
    return await make_game_forum(create, db_session)


@pytest.fixture
async def player(create, db_session, world):
    return await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)


def thread_payload(world, **overrides):
    payload = {"forum_id": world.forum.id, "title": "Hello", "body": prose_doc("Hi")}
    payload.update(overrides)
    return payload


ROLL = {"type": "basic", "roll": "1d20", "reason": "Initiative"}


class TestCreateThreadWithAttachments:
    async def test_roll_attaches_to_the_first_post(
        self, auth_as, world, player, db_session
    ):
        client = auth_as(player)

        response = await client.post(
            "/threads",
            json=thread_payload(world, options={"allow_rolls": True}, rolls=[ROLL]),
        )

        assert response.status_code == 200
        thread = await db_session.get(Thread, response.json()["id"])
        roll = await db_session.scalar(select(PostRoll))
        assert roll.post_id == thread.first_post_id

    async def test_roll_without_allow_rolls_creates_no_thread(
        self, auth_as, world, player, db_session
    ):
        client = auth_as(player)

        response = await client.post(
            "/threads", json=thread_payload(world, rolls=[ROLL])
        )

        assert response.status_code == 403
        assert await db_session.scalar(select(func.count()).select_from(Thread)) == 0

    async def test_draw_attaches_to_the_first_post_and_advances_the_deck(
        self, auth_as, world, player, db_session
    ):
        await allow_drawing(db_session, player, world.deck)
        client = auth_as(player)

        response = await client.post(
            "/threads",
            json=thread_payload(
                world,
                options={"allow_draws": True},
                draws=[{"deck_id": world.deck.id, "count": 2, "reason": "Opening"}],
            ),
        )

        assert response.status_code == 200
        thread = await db_session.get(Thread, response.json()["id"])
        draw = await db_session.scalar(select(PostDraw))
        assert draw.post_id == thread.first_post_id
        assert draw.cards == world.deck.order[:2]
        await db_session.refresh(world.deck)
        assert world.deck.position == 2
