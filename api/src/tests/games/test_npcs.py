import io
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import select

from app.configs import configs
from app.games import routes as game_routes
from sqlalchemy.exc import IntegrityError

from app.models import Player, QuickNPC
from app.repositories import (
    GameRepository,
    NPCOwner,
    PlayerRepository,
    QuickNPCRepository,
)
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
async def world(create, db_session):
    return await make_game_forum(create, db_session)


async def add_player(
    create, db_session, game, *, is_gm=False, state=Player.States.ACCEPTED
):
    user = await create(ActivatedUserFactory)
    await PlayerRepository(db_session, principal=user).attach_player_to_game(
        game.id, user.id, is_gm=is_gm, state=state
    )
    return user


@pytest.fixture
async def player(create, db_session, world):
    return await add_player(create, db_session, world.game, is_gm=False)


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


def upload(contents=None):
    return {"image": ("pic.png", contents or png_bytes(), "image/png")}


class TestPlayersOnly:
    # Each endpoint, with the body it needs, so a missing membership check on any
    # one of them shows up.
    ENDPOINTS = [
        ("get", "/games/{game}/images", {}),
        ("post", "/games/{game}/images", {"files": upload()}),
        ("post", "/games/{game}/images/link", {"json": {"url": "http://x.test/a.png"}}),
        ("get", "/games/{game}/npcs", {}),
        ("post", "/games/{game}/npcs", {"json": {"name": "New"}}),
        ("patch", "/games/{game}/npcs/{npc}", {"json": {"name": "New"}}),
        ("delete", "/games/{game}/npcs/{npc}", {}),
    ]

    @pytest.mark.parametrize("method,path,kwargs", ENDPOINTS)
    @pytest.mark.parametrize("membership", ["outsider", "applied"])
    async def test_anyone_not_accepted_is_refused(
        self, auth_as, create, db_session, world, method, path, kwargs, membership
    ):
        npc = await make_npc(db_session, world.game, world.gm)
        if membership == "outsider":
            user = await create(ActivatedUserFactory)
        else:
            user = await add_player(
                create,
                db_session,
                world.game,
                state=Player.States[membership.upper()],
            )
        client = auth_as(user)

        response = await getattr(client, method)(
            path.format(game=world.game.id, npc=npc.id), **kwargs
        )

        assert response.status_code == 403

    async def test_a_plain_player_can_use_the_library(
        self, auth_as, monkeypatch, tmp_path, db_session, world, player
    ):
        monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))
        await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(player)

        uploaded = await client.post(f"/games/{world.game.id}/images", files=upload())
        created = await client.post(
            f"/games/{world.game.id}/npcs",
            json={"name": "Mine", "image_id": uploaded.json()["id"]},
        )
        npcs = await client.get(f"/games/{world.game.id}/npcs")
        images = await client.get(f"/games/{world.game.id}/images")

        assert uploaded.status_code == 200
        assert created.status_code == 200
        assert {n["name"] for n in npcs.json()} == {"Guard", "Mine"}
        assert [i["id"] for i in images.json()] == [uploaded.json()["id"]]

    async def test_unknown_game_is_404(self, auth_as, world):
        client = auth_as(world.gm)

        response = await client.get("/games/99999/npcs")

        assert response.status_code == 404


class TestEditRights:
    async def test_creator_can_edit_and_delete_their_own_pair(
        self, auth_as, db_session, world, player
    ):
        npc = await make_npc(db_session, world.game, player, "Mine")
        client = auth_as(player)

        renamed = await client.patch(
            f"/games/{world.game.id}/npcs/{npc.id}", json={"name": "Renamed"}
        )
        deleted = await client.delete(f"/games/{world.game.id}/npcs/{npc.id}")

        assert renamed.json()["name"] == "Renamed"
        assert deleted.status_code == 204

    async def test_another_player_cannot_edit_or_delete_it(
        self, auth_as, create, db_session, world, player
    ):
        other = await add_player(create, db_session, world.game)
        npc = await make_npc(db_session, world.game, player, "Mine")
        client = auth_as(other)

        renamed = await client.patch(
            f"/games/{world.game.id}/npcs/{npc.id}", json={"name": "Renamed"}
        )
        deleted = await client.delete(f"/games/{world.game.id}/npcs/{npc.id}")

        assert renamed.status_code == 403
        assert deleted.status_code == 403

    async def test_any_gm_can_edit_and_delete_a_players_pair(
        self, auth_as, create, db_session, world, player
    ):
        co_gm = await add_player(create, db_session, world.game, is_gm=True)
        npc = await make_npc(db_session, world.game, player, "Guard")
        client = auth_as(co_gm)

        renamed = await client.patch(
            f"/games/{world.game.id}/npcs/{npc.id}", json={"name": "Captain"}
        )
        deleted = await client.delete(f"/games/{world.game.id}/npcs/{npc.id}")

        assert renamed.json()["name"] == "Captain"
        assert deleted.status_code == 204

    async def test_can_edit_reflects_gm_or_creator(
        self, auth_as, create, db_session, world, player
    ):
        other = await add_player(create, db_session, world.game)
        await make_npc(db_session, world.game, player, "Players")
        await make_npc(db_session, world.game, world.gm, "GMs")

        def flags(response):
            return {n["name"]: n["can_edit"] for n in response.json()}

        as_gm = await auth_as(world.gm).get(f"/games/{world.game.id}/npcs")
        as_creator = await auth_as(player).get(f"/games/{world.game.id}/npcs")
        as_other = await auth_as(other).get(f"/games/{world.game.id}/npcs")

        assert flags(as_gm) == {"Players": True, "GMs": True}
        assert flags(as_creator) == {"Players": True, "GMs": False}
        assert flags(as_other) == {"Players": False, "GMs": False}


class TestCreateNPC:
    async def test_returns_the_existing_pair_instead_of_a_duplicate(
        self, auth_as, db_session, world, player
    ):
        image = await make_game_image(db_session, world.game, world.gm)
        existing = await make_npc(db_session, world.game, world.gm, "Guard", image)
        client = auth_as(player)

        response = await client.post(
            f"/games/{world.game.id}/npcs",
            json={"name": " Guard ", "image_id": image.id},
        )

        assert response.status_code == 200
        assert response.json()["id"] == existing.id
        # It's the GM's pair, so the player gets no edit rights from asking for it.
        assert response.json()["can_edit"] is False

    async def test_image_must_be_in_the_games_library(
        self, auth_as, db_session, world, player
    ):
        other = await world.make_game("Other Campaign")
        foreign = await make_game_image(db_session, other.game, other.gm)
        personal = await make_user_image(db_session, player)
        client = auth_as(player)

        from_game = await client.post(
            f"/games/{world.game.id}/npcs",
            json={"name": "X", "image_id": foreign.id},
        )
        from_user = await client.post(
            f"/games/{world.game.id}/npcs",
            json={"name": "X", "image_id": personal.id},
        )

        assert from_game.status_code == 400
        assert from_user.status_code == 400

    async def test_an_unknown_image_is_rejected(self, auth_as, world, player):
        client = auth_as(player)

        response = await client.post(
            f"/games/{world.game.id}/npcs", json={"name": "X", "image_id": 999999}
        )

        assert response.status_code == 400

    async def test_blank_name_is_rejected(self, auth_as, world, player):
        client = auth_as(player)

        response = await client.post(
            f"/games/{world.game.id}/npcs", json={"name": "   "}
        )

        assert response.status_code == 422


class TestOwnership:
    async def test_a_row_needs_exactly_one_owner(self, db_session, world):
        async def insert(**owner):
            async with db_session.begin_nested():
                db_session.add(QuickNPC(name="X", created_by=world.gm.id, **owner))
                await db_session.flush()

        with pytest.raises(IntegrityError):
            await insert()
        with pytest.raises(IntegrityError):
            await insert(game_id=world.game.id, user_id=world.gm.id)

    async def test_a_game_and_a_user_can_each_hold_the_same_pair(
        self, db_session, world
    ):
        repository = QuickNPCRepository(db_session, principal=world.gm)

        in_game = await repository.get_or_create(
            NPCOwner.game(world.game.id), "Guard", None
        )
        personal = await repository.get_or_create(
            NPCOwner.user(world.gm.id), "Guard", None
        )

        assert in_game.id != personal.id


class TestRetiredGame:
    WRITES = [
        ("post", "/games/{game}/images", {"files": upload()}),
        ("post", "/games/{game}/images/link", {"json": {"url": "http://x.test/a.png"}}),
        ("post", "/games/{game}/npcs", {"json": {"name": "New"}}),
        ("patch", "/games/{game}/npcs/{npc}", {"json": {"name": "New"}}),
        ("delete", "/games/{game}/npcs/{npc}", {}),
    ]

    @pytest.mark.parametrize("method,path,kwargs", WRITES)
    async def test_writes_are_refused(
        self, auth_as, db_session, world, method, path, kwargs
    ):
        npc = await make_npc(db_session, world.game, world.gm)
        await GameRepository(db_session, principal=world.gm).toggle_retire(world.game)
        client = auth_as(world.gm)

        response = await getattr(client, method)(
            path.format(game=world.game.id, npc=npc.id), **kwargs
        )

        assert response.status_code == 403
        assert response.json()["errors"][0]["detail"] == "Game is retired"

    async def test_gm_can_still_read(self, auth_as, db_session, world):
        await make_npc(db_session, world.game, world.gm)
        await GameRepository(db_session, principal=world.gm).toggle_retire(world.game)
        client = auth_as(world.gm)

        npcs = await client.get(f"/games/{world.game.id}/npcs")
        images = await client.get(f"/games/{world.game.id}/images")

        assert npcs.status_code == 200
        assert images.status_code == 200


class TestImages:
    async def test_upload_resizes_stores_and_returns_the_url(
        self, auth_as, monkeypatch, tmp_path, world
    ):
        monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))
        client = auth_as(world.gm)

        response = await client.post(f"/games/{world.game.id}/images", files=upload())

        assert response.status_code == 200
        body = response.json()
        assert body["url"] == f"{configs.AVATARS_ROOT}/npcs/{body['id']}.png"
        with Image.open(tmp_path / "npcs" / f"{body['id']}.png") as saved:
            assert max(saved.size) == 150

    async def test_upload_rejects_a_non_image(
        self, auth_as, monkeypatch, tmp_path, world
    ):
        monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))
        client = auth_as(world.gm)

        response = await client.post(
            f"/games/{world.game.id}/images",
            files={"image": ("a.png", b"nope", "image/png")},
        )

        assert response.status_code == 400

    async def test_link_stores_the_downloaded_copy(
        self, auth_as, monkeypatch, tmp_path, world
    ):
        monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))
        fetched = []

        async def fake_fetch(url):
            fetched.append(url)
            return png_bytes()

        monkeypatch.setattr(game_routes, "fetch_remote_image", fake_fetch)
        client = auth_as(world.gm)

        response = await client.post(
            f"/games/{world.game.id}/images/link",
            json={"url": "https://example.com/a.png"},
        )

        assert response.status_code == 200
        assert fetched == ["https://example.com/a.png"]
        assert (tmp_path / "npcs" / f"{response.json()['id']}.png").exists()

    async def test_library_lists_this_games_images_newest_first(
        self, auth_as, create, db_session, world
    ):
        other = await world.make_game("Other Campaign")
        old = await make_game_image(db_session, world.game, world.gm)
        new = await make_game_image(db_session, world.game, world.gm, "jpg")
        await make_game_image(db_session, other.game, other.gm)
        old.created_at = datetime.now(UTC) - timedelta(days=1)
        await db_session.flush()
        client = auth_as(world.gm)

        response = await client.get(f"/games/{world.game.id}/images")

        assert response.json() == [
            {"id": new.id, "url": f"{configs.AVATARS_ROOT}/npcs/{new.id}.jpg"},
            {"id": old.id, "url": f"{configs.AVATARS_ROOT}/npcs/{old.id}.png"},
        ]


class TestListNPCs:
    async def test_most_recently_used_first_then_by_name(
        self, auth_as, db_session, world
    ):
        image = await make_game_image(db_session, world.game, world.gm)
        never_b = await make_npc(db_session, world.game, world.gm, "B never")
        never_a = await make_npc(db_session, world.game, world.gm, "A never")
        older = await make_npc(db_session, world.game, world.gm, "Older", image)
        newer = await make_npc(db_session, world.game, world.gm, "Newer")
        older.last_used_at = datetime.now(UTC) - timedelta(days=2)
        newer.last_used_at = datetime.now(UTC) - timedelta(days=1)
        await db_session.flush()
        client = auth_as(world.gm)

        response = await client.get(f"/games/{world.game.id}/npcs")

        body = response.json()
        assert [n["id"] for n in body] == [newer.id, older.id, never_a.id, never_b.id]
        assert body[1]["image"] == {
            "id": image.id,
            "url": f"{configs.AVATARS_ROOT}/npcs/{image.id}.png",
        }
        assert body[0]["image"] is None
        assert body[0]["last_used_at"] is not None
        assert body[2]["last_used_at"] is None

    async def test_leaves_out_deleted_and_other_games_npcs(
        self, auth_as, db_session, world
    ):
        other = await world.make_game("Other Campaign")
        keep = await make_npc(db_session, world.game, world.gm, "Keep")
        gone = await make_npc(db_session, world.game, world.gm, "Gone")
        gone.deleted = datetime.now(UTC)
        await make_npc(db_session, other.game, other.gm, "Elsewhere")
        await db_session.flush()
        client = auth_as(world.gm)

        response = await client.get(f"/games/{world.game.id}/npcs")

        assert [n["id"] for n in response.json()] == [keep.id]


class TestUniqueness:
    async def test_get_or_create_reuses_the_live_pair(self, db_session, world):
        image = await make_game_image(db_session, world.game, world.gm)

        first = await make_npc(db_session, world.game, world.gm, "Guard", image)
        again = await make_npc(db_session, world.game, world.gm, "Guard", image)

        assert again.id == first.id

    async def test_same_name_with_a_different_image_is_a_different_npc(
        self, db_session, world
    ):
        image = await make_game_image(db_session, world.game, world.gm)

        with_image = await make_npc(db_session, world.game, world.gm, "Guard", image)
        without = await make_npc(db_session, world.game, world.gm, "Guard")

        assert with_image.id != without.id

    async def test_missing_image_counts_as_equal(self, db_session, world):
        first = await make_npc(db_session, world.game, world.gm, "Guard")
        again = await make_npc(db_session, world.game, world.gm, "Guard")

        assert again.id == first.id
        count = await db_session.scalars(
            select(QuickNPC).where(QuickNPC.game_id == world.game.id)
        )
        assert len(count.all()) == 1

    async def test_names_are_case_sensitive(self, db_session, world):
        lower = await make_npc(db_session, world.game, world.gm, "guard")
        upper = await make_npc(db_session, world.game, world.gm, "Guard")

        assert lower.id != upper.id

    async def test_deleting_frees_the_pair_for_a_new_npc(self, db_session, world):
        repository = QuickNPCRepository(db_session, principal=world.gm)
        old = await make_npc(db_session, world.game, world.gm, "Guard")
        await repository.delete(old)

        new = await make_npc(db_session, world.game, world.gm, "Guard")

        assert new.id != old.id

    async def test_a_game_owner_does_not_reuse_a_personal_npc_of_the_same_name(
        self, db_session, world
    ):
        personal = await make_user_npc(db_session, world.gm, "Guard")

        in_game = await QuickNPCRepository(
            db_session, principal=world.gm
        ).get_or_create(NPCOwner.game(world.game.id), "Guard", None)

        assert in_game.id != personal.id
        assert in_game.game_id == world.game.id
        assert in_game.user_id is None


class TestUpdateNPC:
    async def test_rename_keeps_the_image(self, auth_as, db_session, world):
        image = await make_game_image(db_session, world.game, world.gm)
        npc = await make_npc(db_session, world.game, world.gm, "Guard", image)
        client = auth_as(world.gm)

        response = await client.patch(
            f"/games/{world.game.id}/npcs/{npc.id}", json={"name": "  Captain "}
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Captain"
        assert response.json()["image"]["id"] == image.id

    async def test_image_can_be_changed_then_cleared(self, auth_as, db_session, world):
        image = await make_game_image(db_session, world.game, world.gm)
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(world.gm)

        set_response = await client.patch(
            f"/games/{world.game.id}/npcs/{npc.id}", json={"image_id": image.id}
        )
        cleared = await client.patch(
            f"/games/{world.game.id}/npcs/{npc.id}", json={"image_id": None}
        )

        assert set_response.json()["image"]["id"] == image.id
        assert cleared.json()["image"] is None
        assert cleared.json()["name"] == "Guard"

    async def test_image_from_another_game_is_rejected(
        self, auth_as, db_session, world
    ):
        other = await world.make_game("Other Campaign")
        foreign = await make_game_image(db_session, other.game, other.gm)
        npc = await make_npc(db_session, world.game, world.gm)
        client = auth_as(world.gm)

        response = await client.patch(
            f"/games/{world.game.id}/npcs/{npc.id}", json={"image_id": foreign.id}
        )

        assert response.status_code == 400

    async def test_collision_with_another_live_pair_is_a_conflict(
        self, auth_as, db_session, world
    ):
        await make_npc(db_session, world.game, world.gm, "Guard")
        other = await make_npc(db_session, world.game, world.gm, "Captain")
        client = auth_as(world.gm)

        response = await client.patch(
            f"/games/{world.game.id}/npcs/{other.id}", json={"name": "Guard"}
        )

        assert response.status_code == 409

    async def test_collision_is_with_the_pair_not_just_the_name(
        self, auth_as, db_session, world
    ):
        image = await make_game_image(db_session, world.game, world.gm)
        await make_npc(db_session, world.game, world.gm, "Guard", image)
        other = await make_npc(db_session, world.game, world.gm, "Captain")
        client = auth_as(world.gm)

        response = await client.patch(
            f"/games/{world.game.id}/npcs/{other.id}", json={"name": "Guard"}
        )

        assert response.status_code == 200

    async def test_saving_an_unchanged_npc_is_not_a_conflict_with_itself(
        self, auth_as, db_session, world
    ):
        npc = await make_npc(db_session, world.game, world.gm, "Guard")
        client = auth_as(world.gm)

        response = await client.patch(
            f"/games/{world.game.id}/npcs/{npc.id}", json={"name": "Guard"}
        )

        assert response.status_code == 200

    @pytest.mark.parametrize("name", [None, "   "])
    async def test_name_cannot_be_blank_or_null(self, auth_as, db_session, world, name):
        npc = await make_npc(db_session, world.game, world.gm)
        client = auth_as(world.gm)

        response = await client.patch(
            f"/games/{world.game.id}/npcs/{npc.id}", json={"name": name}
        )

        assert response.status_code == (400 if name is None else 422)

    async def test_deleted_or_other_games_npc_is_404(self, auth_as, db_session, world):
        other = await world.make_game("Other Campaign")
        foreign = await make_npc(db_session, other.game, other.gm)
        gone = await make_npc(db_session, world.game, world.gm, "Gone")
        gone.deleted = datetime.now(UTC)
        await db_session.flush()
        client = auth_as(world.gm)

        foreign_response = await client.patch(
            f"/games/{world.game.id}/npcs/{foreign.id}", json={"name": "X"}
        )
        gone_response = await client.patch(
            f"/games/{world.game.id}/npcs/{gone.id}", json={"name": "X"}
        )

        assert foreign_response.status_code == 404
        assert gone_response.status_code == 404


class TestDeleteNPC:
    async def test_soft_deletes_and_leaves_the_row(self, auth_as, db_session, world):
        npc = await make_npc(db_session, world.game, world.gm)
        client = auth_as(world.gm)

        response = await client.delete(f"/games/{world.game.id}/npcs/{npc.id}")

        assert response.status_code == 204
        row = await db_session.get(QuickNPC, npc.id)
        assert row is not None
        assert row.deleted is not None

    async def test_other_games_npc_is_404(self, auth_as, db_session, world):
        other = await world.make_game("Other Campaign")
        foreign = await make_npc(db_session, other.game, other.gm)
        client = auth_as(world.gm)

        response = await client.delete(f"/games/{world.game.id}/npcs/{foreign.id}")

        assert response.status_code == 404
