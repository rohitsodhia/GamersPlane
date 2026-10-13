import io
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image

from app.configs import configs
from app.me import routes as me_routes
from tests.factories import ActivatedUserFactory
from tests.game_forum import (
    make_game_forum,
    make_game_image,
    make_npc,
    make_user_image,
    make_user_npc,
)


@pytest.fixture(autouse=True)
def _isolate(wrap_in_savepoint):
    """Roll each test back, including the ones that never use the HTTP client."""


@pytest.fixture
async def user(create):
    return await create(ActivatedUserFactory)


@pytest.fixture
async def stranger(create):
    return await create(ActivatedUserFactory)


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


class TestImages:
    async def test_upload_resizes_stores_and_returns_the_url(
        self, auth_as, monkeypatch, tmp_path, user
    ):
        monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))
        client = auth_as(user)

        response = await client.post(
            "/me/images", files={"image": ("pic.png", png_bytes(), "image/png")}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["url"] == f"{configs.AVATARS_ROOT}/npcs/{body['id']}.png"
        with Image.open(tmp_path / "npcs" / f"{body['id']}.png") as saved:
            assert max(saved.size) == 150

    async def test_link_stores_the_downloaded_copy(
        self, auth_as, monkeypatch, tmp_path, user
    ):
        monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))

        async def fake_fetch(url):
            return png_bytes()

        monkeypatch.setattr(me_routes, "fetch_remote_image", fake_fetch)
        client = auth_as(user)

        response = await client.post(
            "/me/images/link", json={"url": "https://example.com/a.png"}
        )

        assert response.status_code == 200
        assert (tmp_path / "npcs" / f"{response.json()['id']}.png").exists()

    async def test_library_lists_only_the_users_own_images_newest_first(
        self, auth_as, create, db_session, user, stranger
    ):
        world = await make_game_forum(create, db_session)
        old = await make_user_image(db_session, user)
        new = await make_user_image(db_session, user, "jpg")
        await make_user_image(db_session, stranger)
        await make_game_image(db_session, world.game, user)
        old.created_at = datetime.now(UTC) - timedelta(days=1)
        await db_session.flush()
        client = auth_as(user)

        response = await client.get("/me/images")

        assert response.json() == [
            {"id": new.id, "url": f"{configs.AVATARS_ROOT}/npcs/{new.id}.jpg"},
            {"id": old.id, "url": f"{configs.AVATARS_ROOT}/npcs/{old.id}.png"},
        ]


class TestListNPCs:
    async def test_lists_only_the_users_live_personal_npcs(
        self, auth_as, create, db_session, user, stranger
    ):
        world = await make_game_forum(create, db_session)
        image = await make_user_image(db_session, user)
        keep = await make_user_npc(db_session, user, "Keep", image)
        gone = await make_user_npc(db_session, user, "Gone")
        gone.deleted = datetime.now(UTC)
        await make_user_npc(db_session, stranger, "Theirs")
        # Made by the user, but it belongs to the game, not to their library.
        await make_npc(db_session, world.game, user, "Game's")
        await db_session.flush()
        client = auth_as(user)

        response = await client.get("/me/npcs")

        assert response.json() == [
            {
                "id": keep.id,
                "name": "Keep",
                "image": {
                    "id": image.id,
                    "url": f"{configs.AVATARS_ROOT}/npcs/{image.id}.png",
                },
                "last_used_at": None,
                "can_edit": False,
            }
        ]


class TestCreateNPC:
    async def test_creates_a_pair_and_returns_the_existing_one_next_time(
        self, auth_as, db_session, user
    ):
        image = await make_user_image(db_session, user)
        client = auth_as(user)
        body = {"name": " Guard ", "image_id": image.id}

        first = await client.post("/me/npcs", json=body)
        again = await client.post("/me/npcs", json=body)

        assert first.status_code == 200
        assert first.json()["name"] == "Guard"
        assert first.json()["image"]["id"] == image.id
        assert again.json()["id"] == first.json()["id"]
        assert len((await client.get("/me/npcs")).json()) == 1

    async def test_the_same_pair_for_two_users_is_two_npcs(
        self, auth_as, user, stranger
    ):
        mine = await auth_as(user).post("/me/npcs", json={"name": "Guard"})
        theirs = await auth_as(stranger).post("/me/npcs", json={"name": "Guard"})

        assert mine.json()["id"] != theirs.json()["id"]

    async def test_image_must_be_in_the_users_own_library(
        self, auth_as, create, db_session, user, stranger
    ):
        world = await make_game_forum(create, db_session)
        theirs = await make_user_image(db_session, stranger)
        game_image = await make_game_image(db_session, world.game, user)
        client = auth_as(user)

        from_stranger = await client.post(
            "/me/npcs", json={"name": "X", "image_id": theirs.id}
        )
        from_game = await client.post(
            "/me/npcs", json={"name": "X", "image_id": game_image.id}
        )

        assert from_stranger.status_code == 400
        assert from_game.status_code == 400
