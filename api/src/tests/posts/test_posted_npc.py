import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.configs import configs
from app.models import Player, Post, QuickNPC, Thread
from app.repositories import PlayerRepository
from tests.factories import ForumFactory, PostFactory, ThreadFactory, prose_doc
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

WEBHOOK_URL = "https://discord.com/api/webhooks/123456789/abc-DEF_123"


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
        await db_session.scalars(select(QuickNPC).where(QuickNPC.game_id == game_id))
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
        assert post.posted_npc.last_used_at is not None

    async def test_a_player_who_is_not_gm_can_post_as_a_game_npc(
        self, auth_as, db_session, world, player, thread
    ):
        image = await make_game_image(db_session, world.game, world.gm)
        client = auth_as(player)

        response = await client.post(
            "/posts",
            json=new_post(thread, posted_npc={"name": "Guard", "image_id": image.id}),
        )

        assert response.status_code == 200
        post = await db_session.get(Post, response.json()["id"])
        assert post.posted_npc.game_id == world.game.id
        assert post.posted_npc.user_id is None
        assert post.posted_npc.created_by == player.id

    @pytest.mark.parametrize("state", [None, Player.States.APPLIED])
    async def test_someone_who_is_not_an_accepted_player_is_rejected(
        self, auth_as, db_session, world, outsider, thread, state
    ):
        if state is not None:
            await PlayerRepository(
                db_session, principal=outsider
            ).attach_player_to_game(world.game.id, outsider.id, state=state)
        client = auth_as(outsider)

        response = await client.post(
            "/posts", json=new_post(thread, posted_npc={"name": "Guard"})
        )

        assert response.status_code == 400
        assert await npc_posts(db_session, world.game.id) == []

    async def test_a_non_game_forum_uses_the_posters_personal_library(
        self, auth_as, create, db_session
    ):
        forum = await create(ForumFactory, heritage=[0])
        user = await make_user_with(create, db_session, forum, *PLAYER_VERBS)
        image = await make_user_image(db_session, user)
        existing = await make_user_npc(db_session, user, "Guard", image)
        plain_thread = await create(ThreadFactory, forum=forum)
        client = auth_as(user)

        reused = await client.post(
            "/posts",
            json=new_post(
                plain_thread, posted_npc={"name": "Guard", "image_id": image.id}
            ),
        )
        made = await client.post(
            "/posts", json=new_post(plain_thread, posted_npc={"name": "Other"})
        )

        assert reused.status_code == 200
        reused_post = await db_session.get(Post, reused.json()["id"])
        assert reused_post.posted_npc_id == existing.id
        made_post = await db_session.get(Post, made.json()["id"])
        assert made_post.posted_npc.user_id == user.id
        assert made_post.posted_npc.game_id is None

    async def test_a_game_forum_rejects_a_personal_image(
        self, auth_as, db_session, world, thread
    ):
        personal = await make_user_image(db_session, world.gm)
        client = auth_as(world.gm)

        response = await client.post(
            "/posts",
            json=new_post(
                thread, posted_npc={"name": "Guard", "image_id": personal.id}
            ),
        )

        assert response.status_code == 400
        assert await npc_posts(db_session, world.game.id) == []

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

    async def test_after_leaving_the_game_an_unchanged_npc_passes_but_a_changed_one_is_rejected(
        self, auth_as, create, db_session, world, thread, player
    ):
        npc = await make_npc(db_session, world.game, player, "Guard")
        post = await post_as_npc(create, thread, player, npc)
        membership = await PlayerRepository(db_session, principal=player).get_player(
            world.game.id, player.id
        )
        membership.state = Player.States.INVITED
        await db_session.flush()
        client = auth_as(player)

        unchanged = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_npc={"name": "Guard"})
        )
        changed = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_npc={"name": "Other"})
        )

        assert unchanged.status_code == 200
        assert changed.status_code == 400
        await db_session.refresh(post)
        assert post.posted_npc_id == npc.id

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

    async def test_a_renamed_then_deleted_npc_still_shows_on_its_old_posts(
        self, auth_as, create, db_session, world, thread
    ):
        image = await make_game_image(db_session, world.game, world.gm)
        npc = await make_npc(db_session, world.game, world.gm, "Guard", image)
        post = await post_as_npc(create, thread, world.gm, npc)
        client = auth_as(world.gm)
        renamed = await client.patch(
            f"/games/{world.game.id}/npcs/{npc.id}", json={"name": "Captain"}
        )
        renamed_listing = await client.get("/posts", params={"thread_id": thread.id})
        deleted = await client.delete(f"/games/{world.game.id}/npcs/{npc.id}")

        listing = await client.get("/posts", params={"thread_id": thread.id})
        single = await client.get(f"/posts/{post.id}")

        assert renamed.status_code == 200
        assert renamed_listing.json()["posts"][0]["posted_npc"]["name"] == "Captain"
        assert deleted.status_code == 204
        assert listing.json()["posts"][0]["posted_npc"]["name"] == "Captain"
        assert listing.json()["posts"][0]["posted_npc"]["image"] is not None
        assert single.json()["posted_npc"]["id"] == npc.id


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
