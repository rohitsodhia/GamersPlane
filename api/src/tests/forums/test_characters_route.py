from datetime import UTC, datetime

import pytest

from app.models import RolePermission
from tests.factories import ForumFactory, PostFactory, ThreadFactory
from tests.game_forum import (
    PLAYER_VERBS,
    make_character,
    make_game_forum,
    make_user_with,
)

Verbs = RolePermission.ValidPermissions


@pytest.fixture
async def world(create, db_session):
    return await make_game_forum(create, db_session)


@pytest.fixture
async def player(create, db_session, world):
    return await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)


def names(response):
    return [character["name"] for character in response.json()["characters"]]


class TestGetForumCharacters:
    async def test_non_game_forum_has_no_characters(self, auth_as, create, db_session):
        forum = await create(ForumFactory, heritage=[])
        user = await make_user_with(create, db_session, forum, *PLAYER_VERBS)
        await make_character(db_session, user, name="Aria", approved=True, game_id=None)
        client = auth_as(user)

        response = await client.get(f"/forums/{forum.id}/characters")

        assert response.status_code == 200
        assert response.json() == {"characters": [], "default_id": None}

    async def test_player_sees_only_own_approved_named_characters_in_the_game(
        self, auth_as, create, db_session, world, player
    ):
        other = await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)
        other_game = await world.make_game("Other Campaign")
        mine = await make_character(db_session, player, world.game, name="Mine")
        await make_character(
            db_session, player, world.game, name="Pending", approved=False
        )
        await make_character(db_session, player, world.game, name="   ")
        await make_character(db_session, player, world.game, name=None)
        await make_character(db_session, player, other_game.game, name="Elsewhere")
        await make_character(
            db_session, player, world.game, name="Gone", deleted=datetime.now(UTC)
        )
        await make_character(db_session, other, world.game, name="Theirs")
        client = auth_as(player)

        response = await client.get(f"/forums/{world.forum.id}/characters")

        assert response.status_code == 200
        [entry] = response.json()["characters"]
        assert entry == {
            "id": mine.id,
            "name": "Mine",
            "owner": {"id": player.id, "username": player.username},
        }

    async def test_gm_also_sees_other_players_characters_own_first(
        self, auth_as, create, db_session, world, player
    ):
        await make_character(db_session, world.gm, world.game, name="Zed")
        await make_character(db_session, world.gm, world.game, name="Bob")
        await make_character(db_session, player, world.game, name="Aria")
        await make_character(
            db_session, player, world.game, name="Pending", approved=False
        )
        client = auth_as(world.gm)

        response = await client.get(f"/forums/{world.forum.id}/characters")

        assert names(response) == ["Bob", "Zed", "Aria"]
        owners = [c["owner"]["id"] for c in response.json()["characters"]]
        assert owners == [world.gm.id, world.gm.id, player.id]

    async def test_without_write_has_no_characters(
        self, auth_as, create, db_session, world
    ):
        reader = await make_user_with(create, db_session, world.forum, Verbs.FORUM_READ)
        await make_character(db_session, reader, world.game, name="Aria")
        client = auth_as(reader)

        response = await client.get(f"/forums/{world.forum.id}/characters")

        assert response.status_code == 200
        assert response.json()["characters"] == []

    async def test_moderator_without_write_still_gets_characters(
        self, auth_as, create, db_session, world
    ):
        moderator = await make_user_with(
            create, db_session, world.forum, Verbs.FORUM_MODERATE
        )
        await make_character(db_session, moderator, world.game, name="Aria")
        client = auth_as(moderator)

        response = await client.get(f"/forums/{world.forum.id}/characters")

        assert names(response) == ["Aria"]


class TestDefaultCharacter:
    async def thread_with_last_post_as(self, create, db_session, world, user, *chars):
        """A thread where ``user`` posted as each of ``chars`` in turn."""
        thread = await create(ThreadFactory, forum=world.forum)
        for character in chars:
            await create(
                PostFactory,
                thread=thread,
                author=user,
                posted_as=character,
                posted_as_id=character.id if character else None,
            )
        return thread

    async def test_default_is_the_last_post_in_the_thread(
        self, auth_as, create, db_session, world, player
    ):
        first = await make_character(db_session, player, world.game, name="First")
        second = await make_character(db_session, player, world.game, name="Second")
        thread = await self.thread_with_last_post_as(
            create, db_session, world, player, second, first
        )
        client = auth_as(player)

        response = await client.get(
            f"/forums/{world.forum.id}/characters", params={"thread_id": thread.id}
        )

        assert response.json()["default_id"] == first.id

    async def test_last_post_as_the_user_themselves_gives_no_default(
        self, auth_as, create, db_session, world, player
    ):
        char = await make_character(db_session, player, world.game, name="First")
        thread = await self.thread_with_last_post_as(
            create, db_session, world, player, char, None
        )
        client = auth_as(player)

        response = await client.get(
            f"/forums/{world.forum.id}/characters", params={"thread_id": thread.id}
        )

        assert response.json()["default_id"] is None

    async def test_default_is_null_once_the_character_is_no_longer_an_option(
        self, auth_as, create, db_session, world, player
    ):
        char = await make_character(db_session, player, world.game, name="First")
        thread = await self.thread_with_last_post_as(
            create, db_session, world, player, char
        )
        char.approved = False
        await db_session.flush()
        client = auth_as(player)

        response = await client.get(
            f"/forums/{world.forum.id}/characters", params={"thread_id": thread.id}
        )

        assert response.json()["default_id"] is None

    async def test_thread_from_another_forum_is_ignored(
        self, auth_as, create, db_session, world, player
    ):
        char = await make_character(db_session, player, world.game, name="First")
        other_forum = await create(ForumFactory, heritage=[])
        thread = await create(ThreadFactory, forum=other_forum)
        await create(
            PostFactory,
            thread=thread,
            author=player,
            posted_as=char,
            posted_as_id=char.id,
        )
        client = auth_as(player)

        response = await client.get(
            f"/forums/{world.forum.id}/characters", params={"thread_id": thread.id}
        )

        assert response.json()["default_id"] is None
        assert names(response) == ["First"]

    async def test_other_users_posts_dont_set_the_default(
        self, auth_as, create, db_session, world, player
    ):
        mine = await make_character(db_session, player, world.game, name="Mine")
        thread = await create(ThreadFactory, forum=world.forum)
        await create(
            PostFactory,
            thread=thread,
            author=world.gm,
            posted_as=mine,
            posted_as_id=mine.id,
        )
        client = auth_as(player)

        response = await client.get(
            f"/forums/{world.forum.id}/characters", params={"thread_id": thread.id}
        )

        assert response.json()["default_id"] is None
