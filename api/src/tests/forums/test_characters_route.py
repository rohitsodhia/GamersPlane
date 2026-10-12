from datetime import UTC, datetime

import pytest

from app.configs import configs
from app.models import Character, Player, RolePermission
from app.repositories import CharacterRepository, GameRepository, PlayerRepository
from tests.factories import ForumFactory, PostFactory, ThreadFactory
from tests.game_forum import (
    PLAYER_VERBS,
    add_avatar,
    make_character,
    make_game_forum,
    make_game_image,
    make_npc,
    make_user_image,
    make_user_npc,
    make_user_with,
)

Verbs = RolePermission.ValidPermissions


@pytest.fixture
async def world(create, db_session):
    return await make_game_forum(create, db_session)


@pytest.fixture
async def outsider(create, db_session, world):
    """Can write in the game's forum but isn't a player of the game."""
    return await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)


@pytest.fixture
async def player(create, db_session, world):
    """An accepted, non-GM player of the game."""
    user = await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)
    await PlayerRepository(db_session, principal=user).attach_player_to_game(
        world.game.id, user.id, state=Player.States.ACCEPTED
    )
    return user


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
        assert response.json() == {
            "characters": [],
            "default_id": None,
            "default_avatar_id": None,
            "npcs": [],
            "default_npc_id": None,
            "game_id": None,
            "can_manage_npcs": True,
        }

    async def test_without_write_access_nothing_is_offered(
        self, auth_as, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[])
        user = await make_user_with(create, db_session, forum, Verbs.FORUM_READ)
        await make_user_npc(db_session, user, "Guard")
        client = auth_as(user)

        response = await client.get(f"/forums/{forum.id}/characters")

        assert response.json()["npcs"] == []
        assert response.json()["can_manage_npcs"] is False

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
            "type": "pc",
            "owner": {"id": player.id, "username": player.username},
            "avatars": [],
            "last_used_at": None,
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


class TestPostAsOptions:
    async def test_npc_type_and_avatars_primary_first(
        self, auth_as, db_session, world, player
    ):
        character = await make_character(
            db_session, player, world.game, type=Character.Type.NPC
        )
        first_id = await add_avatar(db_session, character, "png")
        second_id = await add_avatar(db_session, character, "jpg")
        third_id = await add_avatar(db_session, character, "gif")
        await CharacterRepository(db_session, principal=player).set_primary_avatar(
            character, third_id
        )
        client = auth_as(player)

        response = await client.get(f"/forums/{world.forum.id}/characters")

        [entry] = response.json()["characters"]
        assert entry["type"] == "npc"
        assert [(a["id"], a["is_primary"]) for a in entry["avatars"]] == [
            (third_id, True),
            (first_id, False),
            (second_id, False),
        ]
        assert entry["avatars"][0]["url"] == (
            f"{configs.AVATARS_ROOT}/characters/{third_id}.gif"
        )

    async def test_last_used_at_is_the_latest_post_in_the_game_by_the_principal(
        self, auth_as, create, db_session, world, player
    ):
        used = await make_character(db_session, player, world.game, name="Used")
        await make_character(db_session, player, world.game, name="Unused")
        other_game = await world.make_game("Other Campaign")
        other_thread = await create(ThreadFactory, forum=other_game.forum)
        thread = await create(ThreadFactory, forum=world.forum)
        older = datetime(2026, 1, 1, tzinfo=UTC)
        newest = datetime(2026, 3, 1, tzinfo=UTC)
        later_elsewhere = datetime(2026, 6, 1, tzinfo=UTC)
        for author, post_thread, published_at in (
            (player, thread, older),
            (player, thread, newest),
            # Another game's forum and another user's post don't count.
            (player, other_thread, later_elsewhere),
            (world.gm, thread, later_elsewhere),
        ):
            await create(
                PostFactory,
                thread=post_thread,
                author=author,
                posted_as=used,
                posted_as_id=used.id,
                published_at=published_at,
            )
        client = auth_as(player)

        response = await client.get(f"/forums/{world.forum.id}/characters")

        by_name = {c["name"]: c for c in response.json()["characters"]}
        assert by_name["Used"]["last_used_at"].startswith("2026-03-01")
        assert by_name["Unused"]["last_used_at"] is None

    async def test_default_avatar_is_the_one_on_the_last_post_in_the_thread(
        self, auth_as, create, db_session, world, player
    ):
        character = await make_character(db_session, player, world.game)
        await add_avatar(db_session, character, "png")
        second_id = await add_avatar(db_session, character, "jpg")
        thread = await create(ThreadFactory, forum=world.forum)
        await create(
            PostFactory,
            thread=thread,
            author=player,
            posted_as=character,
            posted_as_id=character.id,
            posted_avatar_id=second_id,
        )
        client = auth_as(player)

        response = await client.get(
            f"/forums/{world.forum.id}/characters", params={"thread_id": thread.id}
        )

        assert response.json()["default_id"] == character.id
        assert response.json()["default_avatar_id"] == second_id

    async def test_default_avatar_is_null_when_it_is_no_longer_the_characters(
        self, auth_as, create, db_session, world, player
    ):
        character = await make_character(db_session, player, world.game)
        await add_avatar(db_session, character, "png")
        other = await make_character(db_session, player, world.game, name="Other")
        stray_id = await add_avatar(db_session, other, "jpg")
        thread = await create(ThreadFactory, forum=world.forum)
        await create(
            PostFactory,
            thread=thread,
            author=player,
            posted_as=character,
            posted_as_id=character.id,
            posted_avatar_id=stray_id,
        )
        client = auth_as(player)

        response = await client.get(
            f"/forums/{world.forum.id}/characters", params={"thread_id": thread.id}
        )

        assert response.json()["default_id"] == character.id
        assert response.json()["default_avatar_id"] is None


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


class TestQuickNPCOptions:
    async def test_gm_gets_the_games_live_npcs(self, auth_as, db_session, world):
        # Personal NPCs never show up in a game forum.
        await make_user_npc(db_session, world.gm, "Personal")
        other = await world.make_game("Other Campaign")
        image = await make_game_image(db_session, world.game, world.gm)
        guard = await make_npc(db_session, world.game, world.gm, "Guard", image)
        gone = await make_npc(db_session, world.game, world.gm, "Gone")
        gone.deleted = datetime.now(UTC)
        await make_npc(db_session, other.game, other.gm, "Elsewhere")
        await db_session.flush()
        client = auth_as(world.gm)

        response = await client.get(f"/forums/{world.forum.id}/characters")

        assert response.json()["npcs"] == [
            {
                "id": guard.id,
                "name": "Guard",
                "image": {
                    "id": image.id,
                    "url": f"{configs.AVATARS_ROOT}/npcs/{image.id}.png",
                },
                "last_used_at": None,
                "can_edit": True,
            }
        ]

    async def test_a_player_who_is_not_gm_gets_the_games_npcs(
        self, auth_as, db_session, world, player
    ):
        await make_npc(db_session, world.game, world.gm, "GMs")
        await make_npc(db_session, world.game, player, "Mine")
        client = auth_as(player)

        response = await client.get(f"/forums/{world.forum.id}/characters")

        assert {n["name"]: n["can_edit"] for n in response.json()["npcs"]} == {
            "GMs": False,
            "Mine": True,
        }

    async def test_someone_who_is_not_an_accepted_player_gets_none(
        self, auth_as, db_session, world, outsider
    ):
        await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(outsider)

        response = await client.get(f"/forums/{world.forum.id}/characters")

        assert response.json()["npcs"] == []
        assert response.json()["can_manage_npcs"] is False

    async def test_a_player_can_manage_npcs_and_gets_the_game_id(
        self, auth_as, world, player
    ):
        for user in (world.gm, player):
            response = await auth_as(user).get(f"/forums/{world.forum.id}/characters")

            assert response.json()["game_id"] == world.game.id
            assert response.json()["can_manage_npcs"] is True

    async def test_nobody_can_manage_npcs_in_a_retired_game(
        self, auth_as, db_session, world
    ):
        await GameRepository(db_session, principal=world.gm).toggle_retire(world.game)
        client = auth_as(world.gm)

        response = await client.get(f"/forums/{world.forum.id}/characters")

        assert response.json()["can_manage_npcs"] is False

    async def test_a_non_game_forum_offers_the_principals_personal_npcs(
        self, auth_as, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[])
        user = await make_user_with(create, db_session, forum, *PLAYER_VERBS)
        stranger = await make_user_with(create, db_session, forum, *PLAYER_VERBS)
        image = await make_user_image(db_session, user)
        mine = await make_user_npc(db_session, user, "Guard", image)
        gone = await make_user_npc(db_session, user, "Gone")
        gone.deleted = datetime.now(UTC)
        await make_user_npc(db_session, stranger, "Theirs")
        await db_session.flush()
        client = auth_as(user)

        response = await client.get(f"/forums/{forum.id}/characters")

        assert response.json()["game_id"] is None
        assert response.json()["can_manage_npcs"] is True
        assert response.json()["npcs"] == [
            {
                "id": mine.id,
                "name": "Guard",
                "image": {
                    "id": image.id,
                    "url": f"{configs.AVATARS_ROOT}/npcs/{image.id}.png",
                },
                "last_used_at": None,
                "can_edit": False,
            }
        ]

    async def test_a_non_game_forum_has_no_default_npc_even_after_posting_as_one(
        self, auth_as, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[])
        user = await make_user_with(create, db_session, forum, *PLAYER_VERBS)
        npc = await make_user_npc(db_session, user, "Guard")
        thread = await create(ThreadFactory, forum=forum)
        await create(
            PostFactory,
            thread=thread,
            author=user,
            posted_npc=npc,
            posted_npc_id=npc.id,
        )
        client = auth_as(user)

        response = await client.get(
            f"/forums/{forum.id}/characters", params={"thread_id": thread.id}
        )

        assert response.json()["default_npc_id"] is None

    async def test_default_is_the_npc_the_user_last_posted_as_in_the_thread(
        self, auth_as, create, db_session, world
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        thread = await create(ThreadFactory, forum=world.forum)
        await create(
            PostFactory,
            thread=thread,
            author=world.gm,
            posted_npc=npc,
            posted_npc_id=npc.id,
        )
        client = auth_as(world.gm)

        response = await client.get(
            f"/forums/{world.forum.id}/characters", params={"thread_id": thread.id}
        )

        assert response.json()["default_npc_id"] == npc.id
        assert response.json()["default_id"] is None

    async def test_no_default_once_the_npc_is_deleted(
        self, auth_as, create, db_session, world
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        thread = await create(ThreadFactory, forum=world.forum)
        await create(
            PostFactory,
            thread=thread,
            author=world.gm,
            posted_npc=npc,
            posted_npc_id=npc.id,
        )
        npc.deleted = datetime.now(UTC)
        await db_session.flush()
        client = auth_as(world.gm)

        response = await client.get(
            f"/forums/{world.forum.id}/characters", params={"thread_id": thread.id}
        )

        assert response.json()["default_npc_id"] is None
