import io

import pytest
from PIL import Image

from app.configs import configs
from app.models import Game
from app.repositories import PlayerRepository
from tests.factories import ActivatedUserFactory
from tests.game_forum import make_game_forum

FORGED_NAME = "../../etc/passwd"


@pytest.fixture(autouse=True)
def _isolate(wrap_in_savepoint):
    """Roll each test back, including the ones that never use the HTTP client."""


@pytest.fixture(autouse=True)
def _tmp_avatars(monkeypatch, tmp_path):
    monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))


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
        assert body["url"].startswith(f"{configs.AVATARS_ROOT}/backgrounds/")
        assert stored_file(tmp_path, body["url"]).exists()
        game = await db_session.get(Game, world.game.id)
        assert (
            game.advanced_options["background"]["image"]
            == body["url"].rsplit("/", 1)[1]
        )
        assert (body["position"], body["size"], body["repeat"], body["fixed"]) == (
            "center",
            "cover",
            "no-repeat",
            False,
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
                {"background": {"position": "top left", "size": "contain"}},
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

    async def test_only_the_gm_can_upload(self, auth_as, create, db_session, world):
        member = await create(ActivatedUserFactory)
        await PlayerRepository(db_session, principal=member).attach_player_to_game(
            world.game.id, member.id
        )
        stranger = await create(ActivatedUserFactory)

        for user in (member, stranger):
            response = await auth_as(user).post(
                f"/games/{world.game.id}/background", files=upload()
            )
            assert response.status_code == 403

    async def test_non_image_is_rejected(self, auth_as, world):
        response = await auth_as(world.gm).post(
            f"/games/{world.game.id}/background",
            files={"image": ("a.png", b"nope", "image/png")},
        )

        assert response.status_code == 400


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
                {"background": {"repeat": "repeat-x", "fixed": True}},
            ),
        )

        assert response.status_code == 200
        fetched = (await client.get(f"/games/{world.game.id}")).json()
        assert fetched["advanced_options"]["background"] == {
            **uploaded,
            "repeat": "repeat-x",
            "fixed": True,
        }

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
            json=patch_body(world.game, {"background": {"size": "auto"}}),
        )

        assert response.status_code == 400

    @pytest.mark.parametrize(
        "options",
        [
            {"background": {"size": "bogus"}},
            {"theme": "dark"},
            {"background": {"image": FORGED_NAME}},
        ],
    )
    async def test_invalid_options_are_rejected(self, auth_as, world, options):
        response = await auth_as(world.gm).patch(
            f"/games/{world.game.id}", json=patch_body(world.game, options)
        )

        assert response.status_code == 422


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
