from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.configs import configs
from app.models import GameNPC, Player, Post, Thread
from app.repositories import PlayerRepository
from tests.factories import ForumFactory, PostFactory, ThreadFactory, prose_doc
from tests.game_forum import (
    PLAYER_VERBS,
    add_avatar,
    make_character,
    make_game_forum,
    make_game_image,
    make_npc,
    make_user_with,
)

WEBHOOK_URL = "https://discord.com/api/webhooks/123456789/abc-DEF_123"


@pytest.fixture
async def world(create, db_session):
    return await make_game_forum(create, db_session)


@pytest.fixture
async def player(create, db_session, world):
    return await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)


@pytest.fixture
async def thread(create, world):
    return await create(ThreadFactory, forum=world.forum)


def new_post(thread, **overrides):
    return {
        "thread_id": thread.id,
        "title": "Hello",
        "body": prose_doc("Hi there"),
        **overrides,
    }


def edit_post(**overrides):
    return {"title": "Edited", "body": prose_doc("Edited"), **overrides}


async def npc_posts(db_session, game_id):
    return list(
        await db_session.scalars(select(GameNPC).where(GameNPC.game_id == game_id))
    )


async def post_as_npc(create, thread, author, npc):
    return await create(
        PostFactory,
        thread=thread,
        author=author,
        posted_npc=npc,
        posted_npc_id=npc.id,
    )


class TestCreatePostAsNPC:
    async def test_gm_posts_as_a_new_npc_with_an_image(
        self, auth_as, db_session, world, thread
    ):
        image = await make_game_image(db_session, world.game, world.gm)
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=new_post(thread, posted_npc={"name": " Guard ", "image_id": image.id}),
        )

        assert response.status_code == 200
        post = await db_session.get(Post, response.json()["id"])
        assert post.posted_npc.name == "Guard"
        assert post.posted_npc.image_id == image.id
        assert post.posted_npc.game_id == world.game.id
        assert post.posted_npc.created_by == world.gm.id
        assert post.posted_as_id is None

    async def test_publishing_stamps_last_used_at(
        self, auth_as, db_session, world, thread
    ):
        client = auth_as(world.gm)

        response = await client.post(
            "/posts", json=new_post(thread, posted_npc={"name": "Guard"})
        )

        post = await db_session.get(Post, response.json()["id"])
        assert post.posted_npc.last_used_at is not None

    async def test_the_same_name_and_image_reuse_one_npc(
        self, auth_as, db_session, world, thread
    ):
        image = await make_game_image(db_session, world.game, world.gm)
        client = auth_as(world.gm)
        body = {"name": "Guard", "image_id": image.id}

        first = await client.post("/posts", json=new_post(thread, posted_npc=body))
        second = await client.post("/posts", json=new_post(thread, posted_npc=body))

        first_post = await db_session.get(Post, first.json()["id"])
        second_post = await db_session.get(Post, second.json()["id"])
        assert first_post.posted_npc_id == second_post.posted_npc_id
        assert len(await npc_posts(db_session, world.game.id)) == 1

    async def test_no_image_twice_reuses_one_npc_and_an_image_makes_another(
        self, auth_as, db_session, world, thread
    ):
        image = await make_game_image(db_session, world.game, world.gm)
        client = auth_as(world.gm)

        for body in (
            {"name": "Henchman"},
            {"name": "Henchman", "image_id": None},
            {"name": "Henchman", "image_id": image.id},
        ):
            await client.post("/posts", json=new_post(thread, posted_npc=body))

        assert len(await npc_posts(db_session, world.game.id)) == 2

    async def test_a_deleted_pair_is_made_again_rather_than_reused(
        self, auth_as, db_session, world, thread
    ):
        old = await make_npc(db_session, world.game, world.gm, "Guard")
        old.deleted = datetime.now(UTC)
        await db_session.flush()
        client = auth_as(world.gm)

        response = await client.post(
            "/posts", json=new_post(thread, posted_npc={"name": "Guard"})
        )

        post = await db_session.get(Post, response.json()["id"])
        assert post.posted_npc_id != old.id
        assert post.posted_npc.deleted is None

    async def test_a_co_gm_can_reuse_an_npc_another_gm_made(
        self, auth_as, create, db_session, world, thread
    ):
        co_gm = await create_co_gm(create, db_session, world)
        existing = await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(co_gm)

        response = await client.post(
            "/posts", json=new_post(thread, posted_npc={"name": "Guard"})
        )

        post = await db_session.get(Post, response.json()["id"])
        assert post.posted_npc_id == existing.id

    async def test_a_player_who_is_not_gm_is_rejected(
        self, auth_as, db_session, world, player, thread
    ):
        client = auth_as(player)

        response = await client.post(
            "/posts", json=new_post(thread, posted_npc={"name": "Guard"})
        )

        assert response.status_code == 400
        assert await npc_posts(db_session, world.game.id) == []

    async def test_a_gm_of_another_game_is_rejected(
        self, auth_as, create, db_session, world, thread
    ):
        other = await world.make_game("Other Campaign")
        visitor = await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)
        await PlayerRepository(db_session, principal=visitor).attach_player_to_game(
            other.game.id, visitor.id, is_gm=True, state=Player.States.ACCEPTED
        )
        client = auth_as(visitor)

        response = await client.post(
            "/posts", json=new_post(thread, posted_npc={"name": "Guard"})
        )

        assert response.status_code == 400

    async def test_a_non_game_forum_is_rejected(self, auth_as, create, db_session):
        forum = await create(ForumFactory, heritage=[0])
        user = await make_user_with(create, db_session, forum, *PLAYER_VERBS)
        plain_thread = await create(ThreadFactory, forum=forum)
        client = auth_as(user)

        response = await client.post(
            "/posts", json=new_post(plain_thread, posted_npc={"name": "Guard"})
        )

        assert response.status_code == 400

    async def test_another_games_image_is_rejected(
        self, auth_as, db_session, world, thread
    ):
        other = await world.make_game("Other Campaign")
        foreign = await make_game_image(db_session, other.game, other.gm)
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=new_post(thread, posted_npc={"name": "Guard", "image_id": foreign.id}),
        )

        assert response.status_code == 400
        assert await npc_posts(db_session, world.game.id) == []

    async def test_an_unknown_image_is_rejected(self, auth_as, world, thread):
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=new_post(thread, posted_npc={"name": "Guard", "image_id": 99999}),
        )

        assert response.status_code == 400

    @pytest.mark.parametrize("name", ["", "   ", "x" * 101])
    async def test_a_blank_or_overlong_name_is_rejected(
        self, auth_as, world, thread, name
    ):
        client = auth_as(world.gm)

        response = await client.post(
            "/posts", json=new_post(thread, posted_npc={"name": name})
        )

        assert response.status_code == 422

    async def test_a_character_and_an_npc_together_are_rejected(
        self, auth_as, db_session, world, thread
    ):
        character = await make_character(db_session, world.gm, world.game)
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=new_post(
                thread, posted_as_id=character.id, posted_npc={"name": "Guard"}
            ),
        )

        assert response.status_code == 400

    async def test_an_avatar_with_an_npc_is_rejected(
        self, auth_as, db_session, world, thread
    ):
        character = await make_character(db_session, world.gm, world.game)
        avatar_id = await add_avatar(db_session, character)
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=new_post(
                thread, posted_avatar_id=avatar_id, posted_npc={"name": "Guard"}
            ),
        )

        assert response.status_code == 400


async def create_co_gm(create, db_session, world):
    user = await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)
    await PlayerRepository(db_session, principal=user).attach_player_to_game(
        world.game.id, user.id, is_gm=True, state=Player.States.ACCEPTED
    )
    return user


class TestCreateThreadAsNPC:
    async def test_first_post_is_as_the_npc(self, auth_as, db_session, world):
        image = await make_game_image(db_session, world.game, world.gm)
        client = auth_as(world.gm)

        response = await client.post(
            "/threads",
            json={
                "forum_id": world.forum.id,
                "title": "A thread",
                "body": prose_doc("Text"),
                "posted_npc": {"name": "Narrator", "image_id": image.id},
            },
        )

        assert response.status_code == 200
        thread = await db_session.get(Thread, response.json()["id"])
        first = await db_session.get(Post, thread.first_post_id)
        assert first.posted_npc.name == "Narrator"
        assert first.posted_npc.last_used_at is not None

    async def test_a_player_who_is_not_gm_is_rejected(self, auth_as, world, player):
        client = auth_as(player)

        response = await client.post(
            "/threads",
            json={
                "forum_id": world.forum.id,
                "title": "A thread",
                "body": prose_doc("Text"),
                "posted_npc": {"name": "Narrator"},
            },
        )

        assert response.status_code == 400

    async def test_a_character_and_an_npc_together_are_rejected(
        self, auth_as, db_session, world
    ):
        character = await make_character(db_session, world.gm, world.game)
        client = auth_as(world.gm)

        response = await client.post(
            "/threads",
            json={
                "forum_id": world.forum.id,
                "title": "A thread",
                "body": prose_doc("Text"),
                "posted_as_id": character.id,
                "posted_npc": {"name": "Narrator"},
            },
        )

        assert response.status_code == 400


class TestEditPostAsNPC:
    async def test_absent_keeps_the_npc(
        self, auth_as, create, db_session, world, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm)
        post = await post_as_npc(create, thread, world.gm, npc)
        client = auth_as(world.gm)

        response = await client.patch(f"/posts/{post.id}", json=edit_post())

        assert response.status_code == 200
        await db_session.refresh(post)
        assert post.posted_npc_id == npc.id

    async def test_null_clears_the_npc(
        self, auth_as, create, db_session, world, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm)
        post = await post_as_npc(create, thread, world.gm, npc)
        client = auth_as(world.gm)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_npc=None)
        )

        assert response.status_code == 200
        await db_session.refresh(post)
        assert post.posted_npc_id is None

    async def test_switching_to_another_npc_gets_or_creates_it(
        self, auth_as, create, db_session, world, thread
    ):
        old = await make_npc(db_session, world.game, world.gm, "Old")
        post = await post_as_npc(create, thread, world.gm, old)
        client = auth_as(world.gm)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_npc={"name": "New"})
        )

        assert response.status_code == 200
        await db_session.refresh(post)
        assert post.posted_npc.name == "New"
        assert post.posted_npc.last_used_at is not None

    @pytest.mark.parametrize("send_null_character", [True, False])
    async def test_setting_an_npc_clears_the_character_and_avatar(
        self, auth_as, create, db_session, world, thread, send_null_character
    ):
        character = await make_character(db_session, world.gm, world.game)
        avatar_id = await add_avatar(db_session, character)
        post = await create(
            PostFactory,
            thread=thread,
            author=world.gm,
            posted_as=character,
            posted_as_id=character.id,
            posted_avatar_id=avatar_id,
        )
        client = auth_as(world.gm)

        response = await client.patch(
            f"/posts/{post.id}",
            json=edit_post(
                posted_npc={"name": "Guard"},
                **({"posted_as_id": None} if send_null_character else {}),
            ),
        )

        assert response.status_code == 200
        await db_session.refresh(post)
        assert post.posted_as_id is None
        assert post.posted_avatar_id is None
        assert post.posted_npc.name == "Guard"

    async def test_setting_a_character_clears_the_npc(
        self, auth_as, create, db_session, world, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm)
        character = await make_character(db_session, world.gm, world.game)
        post = await post_as_npc(create, thread, world.gm, npc)
        client = auth_as(world.gm)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_as_id=character.id)
        )

        assert response.status_code == 200
        await db_session.refresh(post)
        assert post.posted_as_id == character.id
        assert post.posted_npc_id is None

    async def test_a_character_and_an_npc_together_are_rejected(
        self, auth_as, create, db_session, world, thread
    ):
        character = await make_character(db_session, world.gm, world.game)
        post = await create(PostFactory, thread=thread, author=world.gm)
        client = auth_as(world.gm)

        response = await client.patch(
            f"/posts/{post.id}",
            json=edit_post(posted_as_id=character.id, posted_npc={"name": "Guard"}),
        )

        assert response.status_code == 400

    async def test_unchanged_npc_is_not_revalidated_after_the_author_stops_being_gm(
        self, auth_as, create, db_session, world, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        post = await post_as_npc(create, thread, world.gm, npc)
        player = await PlayerRepository(db_session, principal=world.gm).get_player(
            world.game.id, world.gm.id
        )
        player.is_gm = False
        await db_session.flush()
        client = auth_as(world.gm)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_npc={"name": "Guard"})
        )

        assert response.status_code == 200
        await db_session.refresh(post)
        assert post.posted_npc_id == npc.id

    async def test_changing_the_npc_after_losing_gm_is_rejected(
        self, auth_as, create, db_session, world, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        post = await post_as_npc(create, thread, world.gm, npc)
        player = await PlayerRepository(db_session, principal=world.gm).get_player(
            world.game.id, world.gm.id
        )
        player.is_gm = False
        await db_session.flush()
        client = auth_as(world.gm)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_npc={"name": "Other"})
        )

        assert response.status_code == 400

    async def test_moderator_cannot_change_someone_elses_npc(
        self, auth_as, create, db_session, world, player, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        post = await post_as_npc(create, thread, player, npc)
        client = auth_as(world.gm)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_npc={"name": "Other"})
        )

        assert response.status_code == 403
        await db_session.refresh(post)
        assert post.posted_npc_id == npc.id


class TestReadPostedNPC:
    async def test_posts_list_includes_the_npc_with_its_image_url(
        self, auth_as, create, db_session, world, player, thread
    ):
        image = await make_game_image(db_session, world.game, world.gm, "jpg")
        npc = await make_npc(db_session, world.game, world.gm, "Guard", image)
        await post_as_npc(create, thread, world.gm, npc)
        client = auth_as(player)

        response = await client.get("/posts", params={"thread_id": thread.id})

        [post] = response.json()["posts"]
        assert post["posted_npc"] == {
            "id": npc.id,
            "name": "Guard",
            "image": f"{configs.AVATARS_ROOT}/npcs/{image.id}.jpg",
        }
        assert post["posted_as"] is None

    async def test_get_post_includes_the_npc_without_an_image(
        self, auth_as, create, db_session, world, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        post = await post_as_npc(create, thread, world.gm, npc)
        client = auth_as(world.gm)

        response = await client.get(f"/posts/{post.id}")

        assert response.json()["posted_npc"] == {
            "id": npc.id,
            "name": "Guard",
            "image": None,
        }

    async def test_a_post_not_as_an_npc_has_null(self, auth_as, create, world, thread):
        await create(PostFactory, thread=thread, author=world.gm)
        client = auth_as(world.gm)

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert response.json()["posts"][0]["posted_npc"] is None

    async def test_a_deleted_npc_still_shows_on_its_old_posts(
        self, auth_as, create, db_session, world, thread
    ):
        image = await make_game_image(db_session, world.game, world.gm)
        npc = await make_npc(db_session, world.game, world.gm, "Guard", image)
        post = await post_as_npc(create, thread, world.gm, npc)
        client = auth_as(world.gm)
        deleted = await client.delete(f"/games/{world.game.id}/npcs/{npc.id}")

        listing = await client.get("/posts", params={"thread_id": thread.id})
        single = await client.get(f"/posts/{post.id}")

        assert deleted.status_code == 204
        assert listing.json()["posts"][0]["posted_npc"]["name"] == "Guard"
        assert listing.json()["posts"][0]["posted_npc"]["image"] is not None
        assert single.json()["posted_npc"]["id"] == npc.id

    async def test_renaming_an_npc_changes_its_old_posts(
        self, auth_as, create, db_session, world, thread
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        await post_as_npc(create, thread, world.gm, npc)
        client = auth_as(world.gm)
        renamed = await client.patch(
            f"/games/{world.game.id}/npcs/{npc.id}", json={"name": "Captain"}
        )
        assert renamed.status_code == 200

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert response.json()["posts"][0]["posted_npc"]["name"] == "Captain"


class TestPostConstraint:
    async def test_the_database_refuses_a_character_and_an_npc_on_one_post(
        self, create, db_session, world, thread
    ):
        character = await make_character(db_session, world.gm, world.game)
        npc = await make_npc(db_session, world.game, world.gm)

        with pytest.raises(IntegrityError):
            async with db_session.begin_nested():
                await create(
                    PostFactory,
                    thread=thread,
                    author=world.gm,
                    posted_as_id=character.id,
                    posted_npc_id=npc.id,
                )


class TestWebhook:
    async def test_webhook_goes_out_under_the_npcs_name_and_image(
        self, auth_as, create, db_session, world, sent_webhooks
    ):
        thread = await create(
            ThreadFactory,
            forum=world.forum,
            options=Thread.Options(discord_webhook=WEBHOOK_URL),
        )
        image = await make_game_image(db_session, world.game, world.gm)
        client = auth_as(world.gm)

        await client.post(
            "/posts",
            json=new_post(thread, posted_npc={"name": "Guard", "image_id": image.id}),
        )

        [(_url, payload)] = sent_webhooks
        assert payload["username"] == "Guard"
        assert payload["avatar_url"] == f"{configs.AVATARS_ROOT}/npcs/{image.id}.png"
        assert payload["embeds"][0]["footer"]["text"] == world.gm.username

    async def test_an_npc_without_an_image_sends_no_avatar(
        self, auth_as, create, world, sent_webhooks
    ):
        thread = await create(
            ThreadFactory,
            forum=world.forum,
            options=Thread.Options(discord_webhook=WEBHOOK_URL),
        )
        client = auth_as(world.gm)

        await client.post("/posts", json=new_post(thread, posted_npc={"name": "Guard"}))

        [(_url, payload)] = sent_webhooks
        assert payload["username"] == "Guard"
        assert "avatar_url" not in payload
