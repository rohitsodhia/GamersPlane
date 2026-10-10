from datetime import UTC, datetime

import pytest

from app.configs import configs
from app.models import Post, Thread
from tests.factories import PostFactory, ThreadFactory, prose_doc
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


async def post_as(create, thread, author, character):
    return await create(
        PostFactory,
        thread=thread,
        author=author,
        posted_as=character,
        posted_as_id=character.id if character else None,
    )


class TestCreatePostAs:
    async def test_own_approved_character_is_stored(
        self, auth_as, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game)
        client = auth_as(player)

        response = await client.post(
            "/posts", json=new_post(thread, posted_as_id=character.id)
        )

        assert response.status_code == 200
        post = await db_session.get(Post, response.json()["id"])
        assert post.posted_as_id == character.id

    async def test_no_character_leaves_it_unset(
        self, auth_as, db_session, player, thread
    ):
        client = auth_as(player)

        response = await client.post("/posts", json=new_post(thread))

        post = await db_session.get(Post, response.json()["id"])
        assert post.posted_as_id is None

    async def test_gm_can_post_as_a_players_character(
        self, auth_as, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game)
        client = auth_as(world.gm)

        response = await client.post(
            "/posts", json=new_post(thread, posted_as_id=character.id)
        )

        assert response.status_code == 200

    async def test_player_cannot_post_as_another_players_character(
        self, auth_as, create, db_session, world, player, thread
    ):
        other = await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)
        character = await make_character(db_session, other, world.game)
        client = auth_as(player)

        response = await client.post(
            "/posts", json=new_post(thread, posted_as_id=character.id)
        )

        assert response.status_code == 400

    async def test_unapproved_character_is_rejected(
        self, auth_as, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game, approved=False)
        client = auth_as(player)

        response = await client.post(
            "/posts", json=new_post(thread, posted_as_id=character.id)
        )

        assert response.status_code == 400

    async def test_character_from_another_game_is_rejected(
        self, auth_as, db_session, world, player, thread
    ):
        other_game = await world.make_game("Other Campaign")
        character = await make_character(db_session, player, other_game.game)
        client = auth_as(player)

        response = await client.post(
            "/posts", json=new_post(thread, posted_as_id=character.id)
        )

        assert response.status_code == 400

    async def test_blank_named_character_is_rejected(
        self, auth_as, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game, name="  ")
        client = auth_as(player)

        response = await client.post(
            "/posts", json=new_post(thread, posted_as_id=character.id)
        )

        assert response.status_code == 400

    async def test_unknown_or_deleted_character_is_rejected(
        self, auth_as, db_session, world, player, thread
    ):
        gone = await make_character(
            db_session, player, world.game, deleted=datetime.now(UTC)
        )
        client = auth_as(player)

        deleted = await client.post(
            "/posts", json=new_post(thread, posted_as_id=gone.id)
        )
        unknown = await client.post(
            "/posts", json=new_post(thread, posted_as_id=999999)
        )

        assert deleted.status_code == 400
        assert unknown.status_code == 400

    async def test_character_in_a_non_game_forum_is_rejected(
        self, auth_as, create, db_session, world, player
    ):
        character = await make_character(db_session, player, world.game)
        plain_thread = await create(ThreadFactory)
        client = auth_as(player)

        response = await client.post(
            "/posts", json=new_post(plain_thread, posted_as_id=character.id)
        )

        assert response.status_code == 400

    async def test_webhook_goes_out_under_the_characters_name_and_avatar(
        self, auth_as, create, db_session, world, player, sent_webhooks
    ):
        thread = await create(
            ThreadFactory,
            forum=world.forum,
            options=Thread.Options(discord_webhook=WEBHOOK_URL),
        )
        character = await make_character(db_session, player, world.game, name="Aria")
        avatar_id = await add_avatar(db_session, character)
        client = auth_as(player)

        await client.post("/posts", json=new_post(thread, posted_as_id=character.id))

        [(_url, payload)] = sent_webhooks
        assert payload["username"] == "Aria"
        assert (
            payload["avatar_url"]
            == f"{configs.AVATARS_ROOT}/characters/{avatar_id}.png"
        )
        assert payload["embeds"][0]["footer"]["text"] == player.username


class TestEditPostAs:
    async def test_absent_leaves_the_character(
        self, auth_as, create, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game)
        post = await post_as(create, thread, player, character)
        client = auth_as(player)

        response = await client.patch(f"/posts/{post.id}", json=edit_post())

        assert response.status_code == 200
        await db_session.refresh(post)
        assert post.posted_as_id == character.id

    async def test_null_clears_the_character(
        self, auth_as, create, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game)
        post = await post_as(create, thread, player, character)
        client = auth_as(player)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_as_id=None)
        )

        assert response.status_code == 200
        await db_session.refresh(post)
        assert post.posted_as_id is None

    async def test_can_switch_to_another_valid_character(
        self, auth_as, create, db_session, world, player, thread
    ):
        old = await make_character(db_session, player, world.game, name="Old")
        new = await make_character(db_session, player, world.game, name="New")
        post = await post_as(create, thread, player, old)
        client = auth_as(player)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_as_id=new.id)
        )

        assert response.status_code == 200
        await db_session.refresh(post)
        assert post.posted_as_id == new.id

    async def test_changing_to_an_invalid_character_is_rejected(
        self, auth_as, create, db_session, world, player, thread
    ):
        pending = await make_character(db_session, player, world.game, approved=False)
        post = await post_as(create, thread, player, None)
        client = auth_as(player)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_as_id=pending.id)
        )

        assert response.status_code == 400

    async def test_unchanged_stale_character_is_not_revalidated(
        self, auth_as, create, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game)
        post = await post_as(create, thread, player, character)
        await db_session.refresh(character)
        character.game_id = None
        character.approved = False
        await db_session.flush()
        client = auth_as(player)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_as_id=character.id)
        )

        assert response.status_code == 200
        await db_session.refresh(post)
        assert post.posted_as_id == character.id

    async def test_moderator_cannot_change_someone_elses_character(
        self, auth_as, create, db_session, world, player, thread
    ):
        mine = await make_character(db_session, player, world.game)
        gm_character = await make_character(db_session, world.gm, world.game)
        post = await post_as(create, thread, player, mine)
        client = auth_as(world.gm)

        response = await client.patch(
            f"/posts/{post.id}", json=edit_post(posted_as_id=gm_character.id)
        )

        assert response.status_code == 403
        await db_session.refresh(post)
        assert post.posted_as_id == mine.id

    async def test_moderator_edit_leaving_it_absent_is_fine(
        self, auth_as, create, db_session, world, player, thread
    ):
        mine = await make_character(db_session, player, world.game)
        post = await post_as(create, thread, player, mine)
        client = auth_as(world.gm)

        response = await client.patch(f"/posts/{post.id}", json=edit_post())

        assert response.status_code == 200


class TestReadPostedAs:
    async def test_posts_list_includes_the_character_with_avatar(
        self, auth_as, create, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game, name="Aria")
        first_id = await add_avatar(db_session, character, "png")
        await add_avatar(db_session, character, "jpg")
        await post_as(create, thread, player, character)
        client = auth_as(player)

        response = await client.get("/posts", params={"thread_id": thread.id})

        [post] = response.json()["posts"]
        assert post["posted_as"] == {
            "id": character.id,
            "name": "Aria",
            "avatar": f"{configs.AVATARS_ROOT}/characters/{first_id}.png",
            "can_view": True,
        }

    async def test_character_without_an_avatar_has_a_null_avatar(
        self, auth_as, create, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game)
        await post_as(create, thread, player, character)
        client = auth_as(player)

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert response.json()["posts"][0]["posted_as"]["avatar"] is None

    async def test_post_without_a_character_has_null_posted_as(
        self, auth_as, create, player, thread
    ):
        await post_as(create, thread, player, None)
        client = auth_as(player)

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert response.json()["posts"][0]["posted_as"] is None

    async def test_get_post_includes_the_character(
        self, auth_as, create, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game, name="Aria")
        post = await post_as(create, thread, player, character)
        client = auth_as(player)

        response = await client.get(f"/posts/{post.id}")

        assert response.json()["posted_as"]["name"] == "Aria"

    async def test_owner_and_gm_can_view_but_another_player_cannot(
        self, auth_as, create, db_session, world, player, thread
    ):
        stranger = await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)
        character = await make_character(db_session, player, world.game)
        await post_as(create, thread, player, character)

        def can_view(response):
            return response.json()["posts"][0]["posted_as"]["can_view"]

        params = {"thread_id": thread.id}
        assert can_view(await auth_as(player).get("/posts", params=params)) is True
        assert can_view(await auth_as(world.gm).get("/posts", params=params)) is True
        assert can_view(await auth_as(stranger).get("/posts", params=params)) is False

    async def test_library_character_is_viewable_by_anyone(
        self, auth_as, create, db_session, world, player, thread
    ):
        stranger = await make_user_with(create, db_session, world.forum, *PLAYER_VERBS)
        character = await make_character(
            db_session, player, world.game, in_library=True
        )
        await post_as(create, thread, player, character)
        client = auth_as(stranger)

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert response.json()["posts"][0]["posted_as"]["can_view"] is True

    async def test_deleted_character_reads_as_null(
        self, auth_as, create, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game)
        post = await post_as(create, thread, player, character)
        character.deleted = datetime.now(UTC)
        await db_session.flush()
        db_session.expire(post)
        db_session.expire(character)
        client = auth_as(player)

        listing = await client.get("/posts", params={"thread_id": thread.id})
        single = await client.get(f"/posts/{post.id}")

        assert listing.json()["posts"][0]["posted_as"] is None
        assert single.json()["posted_as"] is None

    async def test_blank_named_character_reads_as_null(
        self, auth_as, create, db_session, world, player, thread
    ):
        character = await make_character(db_session, player, world.game)
        post = await post_as(create, thread, player, character)
        character.name = "   "
        await db_session.flush()
        db_session.expire(post)
        db_session.expire(character)
        client = auth_as(player)

        response = await client.get("/posts", params={"thread_id": thread.id})

        assert response.json()["posts"][0]["posted_as"] is None
