from datetime import UTC, datetime

import pytest

from app.configs import configs
from app.models import Player, Post
from app.repositories import PlayerRepository
from tests.factories import ForumFactory, PostFactory, ThreadFactory
from tests.game_forum import (
    PLAYER_VERBS,
    make_game_forum,
    make_game_image,
    make_npc,
    make_user_npc,
    make_user_with,
)


def speaker(npc_id, text="Hello"):
    return {
        "type": "npcSpeaker",
        "attrs": {"npcId": npc_id},
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


@pytest.fixture
async def world(create, db_session):
    return await make_game_forum(create, db_session)


@pytest.fixture
async def player(create, db_session, world):
    """An accepted, non-GM player of the game."""
    user = await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)
    await PlayerRepository(db_session, principal=user).attach_player_to_game(
        world.game.id, user.id, state=Player.States.ACCEPTED
    )
    return user


@pytest.fixture
async def thread(create, world):
    return await create(ThreadFactory, forum=world.forum)


@pytest.fixture
async def plain_forum_user(create, db_session):
    """A user with write access in a non-game forum, plus the forum."""
    forum = await create(ForumFactory, heritage=[0])
    user = await make_user_with(create, db_session, forum, *PLAYER_VERBS)
    return user, forum


def new_post(thread, body):
    return {"thread_id": thread.id, "title": "Hello", "body": body}


def new_thread(forum, body):
    return {"forum_id": forum.id, "title": "Hello", "body": body}


async def delete_npc(db_session, npc):
    npc.deleted = datetime.now(UTC)
    await db_session.flush()


class TestWriteValidation:
    async def test_a_player_can_use_a_game_npc_in_a_post(
        self, auth_as, db_session, world, player, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(player)

        response = await client.post(
            "/posts", json=new_post(thread, doc(speaker(npc.id)))
        )

        assert response.status_code == 200
        post = await db_session.get(Post, response.json()["id"])
        assert post.body["content"][0]["attrs"] == {"npcId": npc.id}

    async def test_an_npc_of_another_game_is_rejected(
        self, auth_as, db_session, world, thread
    ):
        other = await world.make_game("Other Campaign")
        foreign = await make_npc(db_session, other.game, other.gm, "Spy")
        client = auth_as(world.gm)

        response = await client.post(
            "/posts", json=new_post(thread, doc(speaker(foreign.id)))
        )

        assert response.status_code == 400

    async def test_a_non_player_is_rejected_in_a_game_forum(
        self, auth_as, create, db_session, world, thread
    ):
        outsider = await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(outsider)

        response = await client.post(
            "/posts", json=new_post(thread, doc(speaker(npc.id)))
        )

        assert response.status_code == 400

    async def test_a_personal_npc_works_outside_game_forums(
        self, auth_as, create, db_session, plain_forum_user
    ):
        user, forum = plain_forum_user
        stranger = await make_user_with(create, db_session, forum, *PLAYER_VERBS)
        mine = await make_user_npc(db_session, user, "Guard")
        theirs = await make_user_npc(db_session, stranger, "Guard")
        plain_thread = await create(ThreadFactory, forum=forum)
        client = auth_as(user)

        own = await client.post(
            "/posts", json=new_post(plain_thread, doc(speaker(mine.id)))
        )
        someone_elses = await client.post(
            "/posts", json=new_post(plain_thread, doc(speaker(theirs.id)))
        )

        assert own.status_code == 200
        assert someone_elses.status_code == 400

    async def test_a_deleted_npc_is_rejected_when_new(
        self, auth_as, db_session, world, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        await delete_npc(db_session, npc)
        client = auth_as(world.gm)

        response = await client.post(
            "/posts", json=new_post(thread, doc(speaker(npc.id)))
        )

        assert response.status_code == 400

    async def test_a_malformed_id_is_rejected(self, auth_as, world, thread):
        block = {"type": "npcSpeaker", "attrs": {"npcId": "3"}, "content": []}
        client = auth_as(world.gm)

        response = await client.post("/posts", json=new_post(thread, doc(block)))

        assert response.status_code == 400

    async def test_a_new_thread_checks_its_speakers(self, auth_as, db_session, world):
        other = await world.make_game("Other Campaign")
        foreign = await make_npc(db_session, other.game, other.gm, "Spy")
        mine = await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(world.gm)

        rejected = await client.post(
            "/threads", json=new_thread(world.forum, doc(speaker(foreign.id)))
        )
        accepted = await client.post(
            "/threads", json=new_thread(world.forum, doc(speaker(mine.id)))
        )

        assert rejected.status_code == 400
        assert accepted.status_code == 200


class TestEditValidation:
    async def test_an_existing_speaker_stays_after_its_npc_is_deleted(
        self, auth_as, create, db_session, world, thread
    ):
        # The author can write in the forum but isn't a player (any more) of the
        # game, and the NPC is deleted: an unchanged speaker isn't revalidated.
        former_player = await make_user_with(
            create, db_session, world.forum, *PLAYER_VERBS
        )
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        post = await create(
            PostFactory,
            thread=thread,
            author=former_player,
            body=doc(speaker(npc.id)),
        )
        await delete_npc(db_session, npc)
        client = auth_as(former_player)

        response = await client.patch(
            f"/posts/{post.id}",
            json={"title": "Edited", "body": doc(speaker(npc.id, "New words"))},
        )

        assert response.status_code == 200

    async def test_a_newly_added_deleted_npc_is_rejected(
        self, auth_as, create, db_session, world, player, thread
    ):
        kept = await make_npc(db_session, world.game, world.gm, "Guard")
        gone = await make_npc(db_session, world.game, world.gm, "Ghost")
        post = await create(
            PostFactory, thread=thread, author=player, body=doc(speaker(kept.id))
        )
        await delete_npc(db_session, gone)
        client = auth_as(player)

        response = await client.patch(
            f"/posts/{post.id}",
            json={"title": "Edited", "body": doc(speaker(kept.id), speaker(gone.id))},
        )

        assert response.status_code == 400

    async def test_a_newly_added_live_npc_is_accepted(
        self, auth_as, create, db_session, world, player, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        post = await create(PostFactory, thread=thread, author=player)
        client = auth_as(player)

        response = await client.patch(
            f"/posts/{post.id}",
            json={"title": "Edited", "body": doc(speaker(npc.id))},
        )

        assert response.status_code == 200

    async def test_a_moderator_adding_a_speaker_is_checked_against_the_author(
        self, auth_as, create, db_session, world, thread
    ):
        # The GM (a member, who could use the NPC themselves) adds a game NPC to
        # the post of someone who isn't a player: checked as the author, it fails.
        non_player = await make_user_with(
            create, db_session, world.forum, *PLAYER_VERBS
        )
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        post = await create(PostFactory, thread=thread, author=non_player)
        client = auth_as(world.gm)

        response = await client.patch(
            f"/posts/{post.id}",
            json={"title": "Edited", "body": doc(speaker(npc.id))},
        )

        assert response.status_code == 400


def roster(npc_ids, title="Cast"):
    return {"type": "npcRoster", "attrs": {"title": title, "npcIds": npc_ids}}


class TestRosterValidation:
    async def test_a_player_can_roster_game_npcs(
        self, auth_as, db_session, world, player, thread
    ):
        guard = await make_npc(db_session, world.game, world.gm, "Guard")
        thief = await make_npc(db_session, world.game, world.gm, "Thief")
        client = auth_as(player)

        response = await client.post(
            "/posts", json=new_post(thread, doc(roster([thief.id, guard.id])))
        )

        assert response.status_code == 200
        post = await db_session.get(Post, response.json()["id"])
        assert post.body["content"][0]["attrs"] == {
            "title": "Cast",
            "npcIds": [thief.id, guard.id],
        }

    async def test_one_foreign_id_rejects_the_roster(
        self, auth_as, db_session, world, thread
    ):
        other = await world.make_game("Other Campaign")
        foreign = await make_npc(db_session, other.game, other.gm, "Spy")
        mine = await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(world.gm)

        response = await client.post(
            "/posts", json=new_post(thread, doc(roster([mine.id, foreign.id])))
        )

        assert response.status_code == 400

    async def test_an_empty_roster_is_rejected(self, auth_as, world, thread):
        client = auth_as(world.gm)

        response = await client.post("/posts", json=new_post(thread, doc(roster([]))))

        assert response.status_code == 400

    async def test_a_repeated_id_is_rejected(self, auth_as, db_session, world, thread):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(world.gm)

        response = await client.post(
            "/posts", json=new_post(thread, doc(roster([npc.id, npc.id])))
        )

        assert response.status_code == 400

    async def test_the_same_npc_in_two_rosters_is_fine(
        self, auth_as, db_session, world, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=new_post(thread, doc(roster([npc.id]), roster([npc.id], "Again"))),
        )

        assert response.status_code == 200

    async def test_a_title_over_the_limit_is_rejected_but_the_limit_is_fine(
        self, auth_as, db_session, world, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(world.gm)

        too_long = await client.post(
            "/posts", json=new_post(thread, doc(roster([npc.id], "x" * 101)))
        )
        at_limit = await client.post(
            "/posts", json=new_post(thread, doc(roster([npc.id], "x" * 100)))
        )

        assert too_long.status_code == 400
        assert at_limit.status_code == 200

    async def test_a_title_that_is_not_text_is_rejected(
        self, auth_as, db_session, world, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(world.gm)

        response = await client.post(
            "/posts", json=new_post(thread, doc(roster([npc.id], 5)))
        )

        assert response.status_code == 400

    @pytest.mark.parametrize("attrs", [{}, {"npcIds": ["1"]}])
    async def test_malformed_ids_are_rejected(self, auth_as, world, thread, attrs):
        block = {"type": "npcRoster", "attrs": attrs}
        client = auth_as(world.gm)

        response = await client.post("/posts", json=new_post(thread, doc(block)))

        assert response.status_code == 400

    async def test_a_malformed_roster_is_rejected_on_edit_even_if_old_ids_stay(
        self, auth_as, create, db_session, world, player, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        post = await create(
            PostFactory, thread=thread, author=player, body=doc(roster([npc.id]))
        )
        client = auth_as(player)

        response = await client.patch(
            f"/posts/{post.id}",
            json={"title": "Edited", "body": doc(roster([npc.id, npc.id]))},
        )

        assert response.status_code == 400


class TestContentNpcsInResponses:
    async def test_the_listing_gives_each_speaker_once_with_its_image(
        self, auth_as, create, db_session, world, thread
    ):
        image = await make_game_image(db_session, world.game, world.gm, "jpg")
        guard = await make_npc(db_session, world.game, world.gm, "Guard", image)
        thief = await make_npc(db_session, world.game, world.gm, "Thief")
        bard = await make_npc(db_session, world.game, world.gm, "Bard")
        await create(
            PostFactory,
            thread=thread,
            author=world.gm,
            body=doc(
                speaker(guard.id),
                speaker(thief.id),
                speaker(guard.id),
                roster([bard.id, guard.id]),
            ),
        )
        await create(
            PostFactory, thread=thread, author=world.gm, body=doc(speaker(thief.id))
        )
        client = auth_as(world.gm)

        response = await client.get("/posts", params={"thread_id": thread.id})

        first, second = response.json()["posts"]
        assert first["content_npcs"] == [
            {
                "id": guard.id,
                "name": "Guard",
                "image": {
                    "id": image.id,
                    "url": f"{configs.AVATARS_ROOT}/npcs/{image.id}.jpg",
                },
            },
            {"id": thief.id, "name": "Thief", "image": None},
            {"id": bard.id, "name": "Bard", "image": None},
        ]
        assert [npc["id"] for npc in second["content_npcs"]] == [thief.id]

    async def test_deleted_and_unknown_npcs(
        self, auth_as, create, db_session, world, thread
    ):
        gone = await make_npc(db_session, world.game, world.gm, "Ghost")
        post = await create(
            PostFactory,
            thread=thread,
            author=world.gm,
            body=doc(speaker(gone.id), speaker(987654)),
        )
        await delete_npc(db_session, gone)
        client = auth_as(world.gm)

        listing = await client.get("/posts", params={"thread_id": thread.id})
        single = await client.get(f"/posts/{post.id}")

        for speakers in (
            listing.json()["posts"][0]["content_npcs"],
            single.json()["content_npcs"],
        ):
            assert [(npc["id"], npc["name"]) for npc in speakers] == [
                (gone.id, "Ghost")
            ]
