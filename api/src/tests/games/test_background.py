import io

import pytest
from PIL import Image

from app.configs import configs
from app.models import Game
from tests.factories import ActivatedUserFactory
from tests.game_forum import make_game_forum

FORGED_NAME = "../../etc/passwd"


@pytest.fixture(autouse=True)
def _isolate(wrap_in_savepoint):
    """Roll each test back, including the ones that never use the HTTP client."""


@pytest.fixture(autouse=True)
def _tmp_avatars(monkeypatch, tmp_path):
    monkeypatch.setattr(configs, "BACKGROUNDS_DIR", str(tmp_path / "backgrounds"))


@pytest.fixture
async def world(create, db_session):
    return await make_game_forum(create, db_session)


def upload():
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), color="blue").save(buffer, format="PNG")
    return {"image": ("bg.png", buffer.getvalue(), "image/png")}


def patch_body(game, advanced_options):
    return {
        "title": game.title,
        "system_id": game.system_id,
        "allowed_char_sheets": ["dnd5e"],
        "post_frequency": "3/w",
        "num_players": game.num_players,
        "chars_per_player": game.chars_per_player,
        "description": None,
        "char_gen_info": None,
        "public": game.public,
        "recruitment_thread_id": None,
        "advanced_options": advanced_options,
    }


def stored_file(tmp_path, url):
    return tmp_path / "backgrounds" / url.rsplit("/", 1)[1]


class TestUpload:
    async def test_stores_the_file_and_returns_the_url(
        self, auth_as, db_session, tmp_path, world
    ):
        client = auth_as(world.gm)

        response = await client.post(
            f"/games/{world.game.id}/background", files=upload()
        )

        assert response.status_code == 200
        body = response.json()
        assert body["url"].startswith(f"{configs.BACKGROUNDS_ROOT}/")
        assert stored_file(tmp_path, body["url"]).exists()
        game = await db_session.get(Game, world.game.id)
        assert (
            game.advanced_options["background"]["image"]
            == body["url"].rsplit("/", 1)[1]
        )
        assert (body["position"], body["size"], body["fixed"]) == (
            "top",
            "width",
            True,
        )

    async def test_replacing_deletes_the_old_file_and_keeps_settings(
        self, auth_as, tmp_path, world
    ):
        client = auth_as(world.gm)
        first = (
            await client.post(f"/games/{world.game.id}/background", files=upload())
        ).json()
        await client.patch(
            f"/games/{world.game.id}",
            json=patch_body(
                world.game,
                {
                    "background": {
                        "position": "top left",
                        "size": "contain",
                        "color": "#336699",
                    }
                },
            ),
        )

        second = (
            await client.post(f"/games/{world.game.id}/background", files=upload())
        ).json()

        assert second["url"] != first["url"]
        assert not stored_file(tmp_path, first["url"]).exists()
        assert stored_file(tmp_path, second["url"]).exists()
        assert second["position"] == "top left"
        assert second["size"] == "contain"
        assert second["color"] == "#336699"

    async def test_only_the_gm_can_upload(self, auth_as, create, world):
        stranger = await create(ActivatedUserFactory)

        response = await auth_as(stranger).post(
            f"/games/{world.game.id}/background", files=upload()
        )

        assert response.status_code == 403

    async def test_non_image_is_rejected(self, auth_as, db_session, tmp_path, world):
        response = await auth_as(world.gm).post(
            f"/games/{world.game.id}/background",
            files={"image": ("a.png", b"nope", "image/png")},
        )

        assert response.status_code == 400
        game = await db_session.get(Game, world.game.id)
        assert "background" not in (game.advanced_options or {})
        assert not list((tmp_path / "backgrounds").glob("*"))

    async def test_replacing_when_the_old_file_is_gone_still_succeeds(
        self, auth_as, tmp_path, world
    ):
        client = auth_as(world.gm)
        first = (
            await client.post(f"/games/{world.game.id}/background", files=upload())
        ).json()
        stored_file(tmp_path, first["url"]).unlink()

        response = await client.post(
            f"/games/{world.game.id}/background", files=upload()
        )

        assert response.status_code == 200
        assert stored_file(tmp_path, response.json()["url"]).exists()


class TestSettings:
    async def test_patch_updates_the_settings_and_keeps_the_image(
        self, auth_as, db_session, world
    ):
        client = auth_as(world.gm)
        uploaded = (
            await client.post(f"/games/{world.game.id}/background", files=upload())
        ).json()

        response = await client.patch(
            f"/games/{world.game.id}",
            json=patch_body(
                world.game,
                {"background": {"size": "cover", "fixed": False}},
            ),
        )

        assert response.status_code == 200
        fetched = (await client.get(f"/games/{world.game.id}")).json()
        assert fetched["advanced_options"]["background"] == {
            **uploaded,
            "size": "cover",
            "fixed": False,
        }

    async def test_color_is_set_then_cleared_when_omitted(self, auth_as, world):
        client = auth_as(world.gm)
        await client.post(f"/games/{world.game.id}/background", files=upload())

        await client.patch(
            f"/games/{world.game.id}",
            json=patch_body(world.game, {"background": {"color": "#a1b2c3"}}),
        )
        fetched = (await client.get(f"/games/{world.game.id}")).json()
        assert fetched["advanced_options"]["background"]["color"] == "#a1b2c3"

        await client.patch(
            f"/games/{world.game.id}",
            json=patch_body(world.game, {"background": {"size": "cover"}}),
        )
        fetched = (await client.get(f"/games/{world.game.id}")).json()
        assert fetched["advanced_options"]["background"]["color"] is None

    async def test_patch_without_options_keeps_the_background(self, auth_as, world):
        client = auth_as(world.gm)
        uploaded = (
            await client.post(f"/games/{world.game.id}/background", files=upload())
        ).json()

        response = await client.patch(
            f"/games/{world.game.id}", json=patch_body(world.game, None)
        )

        assert response.status_code == 200
        fetched = (await client.get(f"/games/{world.game.id}")).json()
        assert fetched["advanced_options"]["background"] == uploaded

    async def test_settings_need_an_uploaded_image(self, auth_as, world):
        response = await auth_as(world.gm).patch(
            f"/games/{world.game.id}",
            json=patch_body(world.game, {"background": {"size": "cover"}}),
        )

        assert response.status_code == 400

    @pytest.mark.parametrize(
        "options",
        [
            {"background": {"color": "#fff"}},
            {"background": {"color": "#A1B2C3"}},
            {"theme": "dark"},
            {"background": {"image": FORGED_NAME}},
        ],
    )
    async def test_invalid_options_are_rejected(self, auth_as, world, options):
        response = await auth_as(world.gm).patch(
            f"/games/{world.game.id}", json=patch_body(world.game, options)
        )

        assert response.status_code == 422

    async def test_creating_with_settings_needs_an_uploaded_image(self, auth_as, world):
        response = await auth_as(world.gm).post(
            "/games/",
            json=patch_body(world.game, {"background": {"size": "cover"}}),
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["detail"] == (
            "Upload a background image first"
        )


STORED_IMAGE = "a" * 32 + ".png"
MALFORMED = {"image": "not-a-valid-name", "position": "nowhere"}
LEGACY = {
    "image": STORED_IMAGE,
    "position": "top",
    "size": "width",
    "fixed": True,
    "color": None,
    "repeat": "no-repeat",
}


class TestStoredShapes:
    async def store(self, db_session, game, background):
        game.advanced_options = {"background": background}
        await db_session.flush()

    async def test_legacy_shape_is_read_ignoring_unknown_keys(
        self, auth_as, db_session, world
    ):
        await self.store(db_session, world.game, LEGACY)

        response = await auth_as(world.gm).get(f"/games/{world.game.id}")

        assert response.status_code == 200
        assert response.json()["advanced_options"]["background"] == {
            "position": "top",
            "size": "width",
            "fixed": True,
            "color": None,
            "url": f"{configs.BACKGROUNDS_ROOT}/{STORED_IMAGE}",
        }

    async def test_malformed_background_reads_as_none(self, auth_as, db_session, world):
        await self.store(db_session, world.game, MALFORMED)

        response = await auth_as(world.gm).get(f"/games/{world.game.id}")

        assert response.status_code == 200
        assert response.json()["advanced_options"]["background"] is None

    async def test_settings_need_an_upload_when_the_stored_one_is_malformed(
        self, auth_as, db_session, world
    ):
        await self.store(db_session, world.game, MALFORMED)

        response = await auth_as(world.gm).patch(
            f"/games/{world.game.id}",
            json=patch_body(world.game, {"background": {"size": "cover"}}),
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["detail"] == (
            "Upload a background image first"
        )

    async def test_delete_clears_a_malformed_background(
        self, auth_as, db_session, world
    ):
        await self.store(db_session, world.game, MALFORMED)

        response = await auth_as(world.gm).delete(f"/games/{world.game.id}/background")

        assert response.status_code == 204
        game = await db_session.get(Game, world.game.id)
        assert not game.advanced_options


class TestDelete:
    async def test_removes_the_file_and_the_key(
        self, auth_as, db_session, tmp_path, world
    ):
        client = auth_as(world.gm)
        uploaded = (
            await client.post(f"/games/{world.game.id}/background", files=upload())
        ).json()

        response = await client.delete(f"/games/{world.game.id}/background")

        assert response.status_code == 204
        assert not stored_file(tmp_path, uploaded["url"]).exists()
        game = await db_session.get(Game, world.game.id)
        assert not game.advanced_options
        fetched = (await client.get(f"/games/{world.game.id}")).json()
        assert fetched["advanced_options"] is None

    async def test_without_a_background_is_a_no_op(self, auth_as, world):
        response = await auth_as(world.gm).delete(f"/games/{world.game.id}/background")

        assert response.status_code == 204

    async def test_only_the_gm_can_delete(self, auth_as, create, world):
        stranger = await create(ActivatedUserFactory)

        response = await auth_as(stranger).delete(f"/games/{world.game.id}/background")

        assert response.status_code == 403
