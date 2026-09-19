import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.configs import configs
from app.models import Character, CharacterSheet, FavoriteCharacter
from app.repositories import CharacterRepository, CharacterSheetRepository
from tests.factories import ActivatedUserFactory, SystemFactory

SHEET_LAYOUT = {
    "schema_version": 1,
    "elements": [{"type": "header", "text": "Combat"}],
}


def _make_png_bytes(size=(10, 10)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color="red").save(buffer, format="PNG")
    return buffer.getvalue()


async def _make_sheet(db_session, creator, system, *, status):
    repository = CharacterSheetRepository(db_session, principal=creator)
    sheet = await repository.create(
        name="Fighter", system_id=system.id, layout=SHEET_LAYOUT
    )
    sheet.status = status
    await db_session.flush()
    return sheet


@pytest.fixture
async def system(create):
    return await create(SystemFactory, id="dnd5e", name="D&D 5e")


@pytest.fixture
async def sheet_creator(create):
    return await create(ActivatedUserFactory)


@pytest.fixture
async def public_sheet(db_session, sheet_creator, system, wrap_in_savepoint):
    return await _make_sheet(
        db_session, sheet_creator, system, status=CharacterSheet.Status.PUBLIC
    )


@pytest.fixture
async def private_sheet(db_session, sheet_creator, system, wrap_in_savepoint):
    return await _make_sheet(
        db_session, sheet_creator, system, status=CharacterSheet.Status.PRIVATE
    )


class TestCreateCharacter:
    async def test_requires_auth(self, client, public_sheet):
        response = await client.post(
            "/characters/",
            json={"label": "Aragorn", "character_sheet_id": public_sheet.id},
        )

        assert response.status_code == 403

    async def test_returns_404_when_sheet_missing(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/characters/",
            json={"label": "Aragorn", "character_sheet_id": 999999},
        )

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "not_found"

    async def test_forbids_a_private_sheet_owned_by_someone_else(
        self, client, private_sheet, create, auth_as
    ):
        stranger = await create(ActivatedUserFactory)
        auth_as(stranger)

        response = await client.post(
            "/characters/",
            json={"label": "Aragorn", "character_sheet_id": private_sheet.id},
        )

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "forbidden"

    async def test_creates_a_character_from_a_public_sheet(
        self, client, public_sheet, create, auth_as, db_session
    ):
        user = await create(ActivatedUserFactory)
        auth_as(user)

        response = await client.post(
            "/characters/",
            # Padded label also asserts `label` runs through filtered_str().
            json={"label": "  Aragorn  ", "character_sheet_id": public_sheet.id},
        )

        assert response.status_code == 200
        character = await db_session.get(Character, response.json()["id"])
        assert character is not None
        assert character.user_id == user.id
        assert character.character_sheet_id == public_sheet.id
        assert character.label == "Aragorn"
        assert character.type == Character.Type.PC

    async def test_creator_can_use_their_own_private_sheet(
        self, client, private_sheet, sheet_creator, auth_as
    ):
        auth_as(sheet_creator)

        response = await client.post(
            "/characters/",
            json={"label": "Aragorn", "character_sheet_id": private_sheet.id},
        )

        assert response.status_code == 200

    async def test_stores_the_requested_type(
        self, client, public_sheet, create, auth_as, db_session
    ):
        user = await create(ActivatedUserFactory)
        auth_as(user)

        response = await client.post(
            "/characters/",
            json={
                "label": "The Innkeeper",
                "character_sheet_id": public_sheet.id,
                "type": "npc",
            },
        )

        assert response.status_code == 200
        character = await db_session.get(Character, response.json()["id"])
        assert character.type == Character.Type.NPC


class TestGetCharacter:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def character(self, db_session, owner, public_sheet, wrap_in_savepoint):
        repository = CharacterRepository(db_session, principal=owner)
        return await repository.create(
            character_sheet_id=public_sheet.id,
            label="Aragorn",
            type=Character.Type.PC,
        )

    async def test_requires_auth(self, client, character):
        response = await client.get(f"/characters/{character.id}")

        assert response.status_code == 403

    async def test_returns_404_when_missing(self, authed_client):
        client, _user = authed_client

        response = await client.get("/characters/999999")

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "not_found"

    async def test_returns_the_serialized_character(
        self, client, character, owner, sheet_creator, public_sheet, auth_as
    ):
        auth_as(owner)

        response = await client.get(f"/characters/{character.id}")

        assert response.status_code == 200
        assert response.json() == {
            "id": character.id,
            "user_id": owner.id,
            "label": "Aragorn",
            "name": None,
            "type": "pc",
            "values": None,
            "in_library": False,
            "character_sheet": {
                "id": public_sheet.id,
                "name": "Fighter",
                "creator": {
                    "id": sheet_creator.id,
                    "username": sheet_creator.username,
                    "avatar": sheet_creator.avatar,
                },
                "system": {"id": "dnd5e", "name": "D&D 5e"},
                "layout": SHEET_LAYOUT,
            },
            "avatars": [],
        }

    async def test_forbids_a_non_owner_when_not_in_library(
        self, client, character, create, auth_as
    ):
        stranger = await create(ActivatedUserFactory)
        auth_as(stranger)

        response = await client.get(f"/characters/{character.id}")

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "forbidden"

    async def test_non_owner_can_read_a_library_character(
        self, client, character, create, auth_as, db_session
    ):
        character.in_library = True
        await db_session.flush()
        stranger = await create(ActivatedUserFactory)
        auth_as(stranger)

        response = await client.get(f"/characters/{character.id}")

        assert response.status_code == 200
        assert response.json()["id"] == character.id


class TestGetCharacters:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    async def _make_character(
        self, db_session, owner, sheet, label, type=Character.Type.PC
    ):
        repository = CharacterRepository(db_session, principal=owner)
        return await repository.create(
            character_sheet_id=sheet.id, label=label, type=type
        )

    async def test_requires_auth(self, client):
        response = await client.get("/characters")

        assert response.status_code == 403

    async def test_only_returns_the_principals_characters(
        self, client, public_sheet, owner, create, auth_as, db_session, wrap_in_savepoint
    ):
        stranger = await create(ActivatedUserFactory)
        await self._make_character(db_session, stranger, public_sheet, "Legolas")
        await self._make_character(db_session, owner, public_sheet, "Aragorn")
        auth_as(owner)

        response = await client.get("/characters")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert [c["label"] for c in body["characters"]] == ["Aragorn"]

    async def test_orders_by_system_then_label(
        self, client, owner, sheet_creator, create, auth_as, db_session, wrap_in_savepoint
    ):
        # ids are deliberately the reverse of sort_name, so the assertion
        # below only passes if ordering actually uses System.sort_name.
        system_a = await create(SystemFactory, id="zzz", sort_name="AAA System")
        system_z = await create(SystemFactory, id="aaa", sort_name="ZZZ System")
        sheet_a = await _make_sheet(
            db_session, sheet_creator, system_a, status=CharacterSheet.Status.PUBLIC
        )
        sheet_z = await _make_sheet(
            db_session, sheet_creator, system_z, status=CharacterSheet.Status.PUBLIC
        )
        await self._make_character(db_session, owner, sheet_z, "Zed")
        await self._make_character(db_session, owner, sheet_a, "Beta")
        await self._make_character(db_session, owner, sheet_a, "Alpha")
        auth_as(owner)

        response = await client.get("/characters")

        assert response.status_code == 200
        assert [c["label"] for c in response.json()["characters"]] == [
            "Alpha",
            "Beta",
            "Zed",
        ]

    async def test_filters_by_search(
        self, client, public_sheet, owner, auth_as, db_session, wrap_in_savepoint
    ):
        await self._make_character(db_session, owner, public_sheet, "Aragorn")
        await self._make_character(db_session, owner, public_sheet, "Legolas")
        auth_as(owner)

        response = await client.get("/characters", params={"search": "arag"})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert [c["label"] for c in body["characters"]] == ["Aragorn"]

    async def test_filters_by_type(
        self, client, public_sheet, owner, auth_as, db_session, wrap_in_savepoint
    ):
        await self._make_character(
            db_session, owner, public_sheet, "Aragorn", type=Character.Type.PC
        )
        await self._make_character(
            db_session, owner, public_sheet, "Orc Grunt", type=Character.Type.NPC
        )
        auth_as(owner)

        response = await client.get("/characters", params={"type": "npc"})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert [c["label"] for c in body["characters"]] == ["Orc Grunt"]

    async def test_filters_by_system(
        self, client, owner, sheet_creator, create, auth_as, db_session, wrap_in_savepoint
    ):
        system_a = await create(SystemFactory, id="dnd5e", sort_name="D&D 5e")
        system_b = await create(SystemFactory, id="pf2e", sort_name="Pathfinder 2e")
        sheet_a = await _make_sheet(
            db_session, sheet_creator, system_a, status=CharacterSheet.Status.PUBLIC
        )
        sheet_b = await _make_sheet(
            db_session, sheet_creator, system_b, status=CharacterSheet.Status.PUBLIC
        )
        await self._make_character(db_session, owner, sheet_a, "Aragorn")
        await self._make_character(db_session, owner, sheet_b, "Seelah")
        auth_as(owner)

        response = await client.get("/characters", params={"system_id": "pf2e"})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert [c["label"] for c in body["characters"]] == ["Seelah"]

    async def test_paginates_results(
        self, client, public_sheet, owner, auth_as, db_session, wrap_in_savepoint
    ):
        per_page = configs.PAGINATE_PER_PAGE
        for i in range(per_page + 1):
            await self._make_character(
                db_session, owner, public_sheet, f"Char {i:03}"
            )
        auth_as(owner)

        first_page = await client.get("/characters")
        second_page = await client.get("/characters", params={"page": 2})

        assert first_page.status_code == 200
        assert second_page.status_code == 200
        first_body = first_page.json()
        second_body = second_page.json()
        assert first_body["total"] == per_page + 1
        assert first_body["page"] == 1
        assert len(first_body["characters"]) == per_page
        assert second_body["page"] == 2
        assert len(second_body["characters"]) == 1


class TestGetLibrary:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def viewer(self, create):
        return await create(ActivatedUserFactory)

    async def _make_character(
        self,
        db_session,
        owner,
        sheet,
        label,
        type=Character.Type.PC,
        in_library=True,
    ):
        repository = CharacterRepository(db_session, principal=owner)
        character = await repository.create(
            character_sheet_id=sheet.id, label=label, type=type
        )
        character.in_library = in_library
        await db_session.flush()
        return character

    async def test_requires_auth(self, client):
        response = await client.get("/characters/library")

        assert response.status_code == 403

    async def test_returns_only_id_label_system_and_user(
        self, client, public_sheet, owner, viewer, auth_as, db_session, wrap_in_savepoint
    ):
        character = await self._make_character(
            db_session, owner, public_sheet, "Aragorn"
        )
        auth_as(viewer)

        response = await client.get("/characters/library")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["page"] == 1
        assert body["characters"] == [
            {
                "id": character.id,
                "label": "Aragorn",
                "system": {"id": "dnd5e", "name": "D&D 5e"},
                "user": {"id": owner.id, "username": owner.username},
            }
        ]

    async def test_excludes_own_and_non_library_characters(
        self, client, public_sheet, owner, viewer, auth_as, db_session, wrap_in_savepoint
    ):
        await self._make_character(db_session, owner, public_sheet, "Shared")
        await self._make_character(
            db_session, owner, public_sheet, "Hidden", in_library=False
        )
        await self._make_character(db_session, viewer, public_sheet, "Mine")
        auth_as(viewer)

        response = await client.get("/characters/library")

        body = response.json()
        assert body["total"] == 1
        assert [c["label"] for c in body["characters"]] == ["Shared"]

    async def test_orders_by_system_then_label(
        self, client, owner, viewer, sheet_creator, create, auth_as, db_session, wrap_in_savepoint
    ):
        # ids are deliberately the reverse of sort_name.
        system_a = await create(SystemFactory, id="zzz", sort_name="AAA System")
        system_z = await create(SystemFactory, id="aaa", sort_name="ZZZ System")
        sheet_a = await _make_sheet(
            db_session, sheet_creator, system_a, status=CharacterSheet.Status.PUBLIC
        )
        sheet_z = await _make_sheet(
            db_session, sheet_creator, system_z, status=CharacterSheet.Status.PUBLIC
        )
        await self._make_character(db_session, owner, sheet_z, "Zed")
        await self._make_character(db_session, owner, sheet_a, "Beta")
        await self._make_character(db_session, owner, sheet_a, "Alpha")
        auth_as(viewer)

        response = await client.get("/characters/library")

        assert [c["label"] for c in response.json()["characters"]] == [
            "Alpha",
            "Beta",
            "Zed",
        ]

    async def test_filters_by_search(
        self, client, public_sheet, owner, viewer, auth_as, db_session, wrap_in_savepoint
    ):
        await self._make_character(db_session, owner, public_sheet, "Aragorn")
        await self._make_character(db_session, owner, public_sheet, "Legolas")
        auth_as(viewer)

        response = await client.get("/characters/library", params={"search": "arag"})

        body = response.json()
        assert body["total"] == 1
        assert [c["label"] for c in body["characters"]] == ["Aragorn"]

    async def test_filters_by_type(
        self, client, public_sheet, owner, viewer, auth_as, db_session, wrap_in_savepoint
    ):
        await self._make_character(db_session, owner, public_sheet, "Aragorn")
        await self._make_character(
            db_session, owner, public_sheet, "Orc Grunt", type=Character.Type.NPC
        )
        auth_as(viewer)

        response = await client.get("/characters/library", params={"type": "npc"})

        body = response.json()
        assert body["total"] == 1
        assert [c["label"] for c in body["characters"]] == ["Orc Grunt"]

    async def test_filters_by_multiple_systems(
        self, client, owner, viewer, sheet_creator, create, auth_as, db_session, wrap_in_savepoint
    ):
        for system_id in ("dnd5e", "pf2e", "coc"):
            system = await create(SystemFactory, id=system_id, sort_name=system_id)
            sheet = await _make_sheet(
                db_session, sheet_creator, system, status=CharacterSheet.Status.PUBLIC
            )
            await self._make_character(db_session, owner, sheet, system_id)
        auth_as(viewer)

        response = await client.get(
            "/characters/library", params={"systems": ["dnd5e", "pf2e"]}
        )

        body = response.json()
        assert body["total"] == 2
        assert [c["label"] for c in body["characters"]] == ["dnd5e", "pf2e"]

    async def test_paginates_results(
        self, client, public_sheet, owner, viewer, auth_as, db_session, wrap_in_savepoint
    ):
        per_page = configs.PAGINATE_PER_PAGE
        for i in range(per_page + 1):
            await self._make_character(db_session, owner, public_sheet, f"Char {i:03}")
        auth_as(viewer)

        first = (await client.get("/characters/library")).json()
        second = (await client.get("/characters/library", params={"page": 2})).json()

        assert first["total"] == per_page + 1
        assert first["page"] == 1
        assert len(first["characters"]) == per_page
        assert second["page"] == 2
        assert len(second["characters"]) == 1

    async def test_clamps_page_below_one(
        self, client, public_sheet, owner, viewer, auth_as, db_session, wrap_in_savepoint
    ):
        await self._make_character(db_session, owner, public_sheet, "Aragorn")
        auth_as(viewer)

        response = await client.get("/characters/library", params={"page": 0})

        assert response.status_code == 200
        body = response.json()
        assert body["page"] == 1
        assert len(body["characters"]) == 1


class TestUpdateCharacter:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def character(self, db_session, owner, public_sheet, wrap_in_savepoint):
        repository = CharacterRepository(db_session, principal=owner)
        return await repository.create(
            character_sheet_id=public_sheet.id,
            label="Aragorn",
            type=Character.Type.PC,
        )

    async def test_requires_auth(self, client, character):
        response = await client.patch(
            f"/characters/{character.id}", json={"values": {"str": 18}}
        )

        assert response.status_code == 403

    async def test_returns_404_when_missing(self, authed_client):
        client, _user = authed_client

        response = await client.patch(
            "/characters/999999", json={"values": {"str": 18}}
        )

        assert response.status_code == 404

    async def test_forbids_a_non_owner(self, client, character, create, auth_as):
        stranger = await create(ActivatedUserFactory)
        auth_as(stranger)

        response = await client.patch(
            f"/characters/{character.id}", json={"values": {"str": 18}}
        )

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "forbidden"

    async def test_owner_saves_the_values(
        self, client, character, owner, public_sheet, db_session, auth_as
    ):
        auth_as(owner)
        new_values = {"str": 18, "skills": {"stealth": 3}}

        response = await client.patch(
            f"/characters/{character.id}", json={"values": new_values}
        )

        assert response.status_code == 200
        assert response.json()["values"] == new_values
        # PATCH returns the full sheet-bearing serializer, not just the id.
        assert response.json()["character_sheet"]["id"] == public_sheet.id

        await db_session.refresh(character, ["values"])
        assert character.values == new_values

    async def test_owner_saves_the_label(
        self, client, character, owner, db_session, auth_as
    ):
        auth_as(owner)

        response = await client.patch(
            f"/characters/{character.id}", json={"label": "Strider"}
        )

        assert response.status_code == 200
        assert response.json()["label"] == "Strider"

        await db_session.refresh(character, ["label"])
        assert character.label == "Strider"

    async def test_owner_saves_the_type(
        self, client, character, owner, db_session, auth_as
    ):
        auth_as(owner)

        response = await client.patch(
            f"/characters/{character.id}", json={"type": "npc"}
        )

        assert response.status_code == 200
        assert response.json()["type"] == "npc"

        await db_session.refresh(character, ["type"])
        assert character.type == Character.Type.NPC

    async def test_partial_update_does_not_clear_other_fields(
        self, client, character, owner, db_session, auth_as
    ):
        auth_as(owner)
        await client.patch(f"/characters/{character.id}", json={"values": {"str": 18}})

        response = await client.patch(
            f"/characters/{character.id}", json={"label": "Strider"}
        )

        assert response.status_code == 200
        assert response.json()["label"] == "Strider"
        assert response.json()["type"] == "pc"
        assert response.json()["values"] == {"str": 18}


class TestAddCharacterAvatar:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def character(self, db_session, owner, public_sheet, wrap_in_savepoint):
        repository = CharacterRepository(db_session, principal=owner)
        return await repository.create(
            character_sheet_id=public_sheet.id,
            label="Aragorn",
            type=Character.Type.PC,
        )

    @pytest.fixture(autouse=True)
    def _avatars_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))
        return tmp_path

    async def test_requires_auth(self, client, character):
        response = await client.post(
            f"/characters/{character.id}/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )

        assert response.status_code == 403

    async def test_returns_404_when_character_missing(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/characters/999999/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )

        assert response.status_code == 404

    async def test_forbids_a_non_owner(self, client, character, create, auth_as):
        stranger = await create(ActivatedUserFactory)
        auth_as(stranger)

        response = await client.post(
            f"/characters/{character.id}/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "forbidden"

    async def test_rejects_invalid_image(self, client, character, owner, auth_as):
        auth_as(owner)

        response = await client.post(
            f"/characters/{character.id}/avatar",
            files={"avatar": ("avatar.png", b"not an image", "image/png")},
        )

        assert response.status_code == 400

    async def test_first_upload_is_primary(
        self, client, character, owner, auth_as, _avatars_dir
    ):
        auth_as(owner)

        response = await client.post(
            f"/characters/{character.id}/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["avatar"]["is_primary"] is True
        avatar_id = body["avatar"]["id"]
        assert body["avatar"]["url"] == (
            f"{configs.AVATARS_ROOT}/characters/{avatar_id}.png"
        )
        assert (_avatars_dir / "characters" / f"{avatar_id}.png").exists()

    async def test_second_upload_is_not_primary(
        self, client, character, owner, auth_as
    ):
        auth_as(owner)
        await client.post(
            f"/characters/{character.id}/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )

        response = await client.post(
            f"/characters/{character.id}/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )

        assert response.status_code == 200
        assert response.json()["avatar"]["is_primary"] is False

    async def test_enforces_the_max_avatar_count(
        self, client, character, owner, auth_as
    ):
        auth_as(owner)
        for _ in range(5):
            response = await client.post(
                f"/characters/{character.id}/avatar",
                files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
            )
            assert response.status_code == 200

        response = await client.post(
            f"/characters/{character.id}/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )

        assert response.status_code == 400


class TestDeleteCharacterAvatar:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def character(self, db_session, owner, public_sheet, wrap_in_savepoint):
        repository = CharacterRepository(db_session, principal=owner)
        return await repository.create(
            character_sheet_id=public_sheet.id,
            label="Aragorn",
            type=Character.Type.PC,
        )

    @pytest.fixture(autouse=True)
    def _avatars_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))
        return tmp_path

    async def _add_avatar(self, client, character_id):
        response = await client.post(
            f"/characters/{character_id}/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )
        return response.json()["avatar"]

    async def test_requires_auth(self, client, character):
        response = await client.delete(f"/characters/{character.id}/avatar/1")

        assert response.status_code == 403

    async def test_returns_404_when_character_missing(self, authed_client):
        client, _user = authed_client

        response = await client.delete("/characters/999999/avatar/1")

        assert response.status_code == 404

    async def test_forbids_a_non_owner(self, client, character, owner, auth_as, create):
        auth_as(owner)
        avatar = await self._add_avatar(client, character.id)

        stranger = await create(ActivatedUserFactory)
        auth_as(stranger)
        response = await client.delete(
            f"/characters/{character.id}/avatar/{avatar['id']}"
        )

        assert response.status_code == 403

    async def test_returns_404_when_avatar_missing(
        self, client, character, owner, auth_as
    ):
        auth_as(owner)

        response = await client.delete(f"/characters/{character.id}/avatar/999999")

        assert response.status_code == 404

    async def test_deletes_the_avatar_and_its_file(
        self, client, character, owner, auth_as, _avatars_dir
    ):
        auth_as(owner)
        avatar = await self._add_avatar(client, character.id)
        avatar_path = _avatars_dir / "characters" / f"{avatar['id']}.png"
        assert avatar_path.exists()

        response = await client.delete(
            f"/characters/{character.id}/avatar/{avatar['id']}"
        )

        assert response.status_code == 200
        assert response.json() == {"success": True}
        assert not avatar_path.exists()

    async def test_promotes_another_avatar_to_primary_when_primary_is_deleted(
        self, client, character, owner, auth_as
    ):
        auth_as(owner)
        first = await self._add_avatar(client, character.id)
        second = await self._add_avatar(client, character.id)
        assert first["is_primary"] is True
        assert second["is_primary"] is False

        await client.delete(f"/characters/{character.id}/avatar/{first['id']}")

        response = await client.get(f"/characters/{character.id}")
        avatars = response.json()["avatars"]
        assert len(avatars) == 1
        assert avatars[0]["id"] == second["id"]
        assert avatars[0]["is_primary"] is True

    async def test_deleting_a_non_primary_avatar_leaves_primary_unchanged(
        self, client, character, owner, auth_as
    ):
        auth_as(owner)
        first = await self._add_avatar(client, character.id)
        second = await self._add_avatar(client, character.id)
        assert first["is_primary"] is True
        assert second["is_primary"] is False

        await client.delete(f"/characters/{character.id}/avatar/{second['id']}")

        response = await client.get(f"/characters/{character.id}")
        avatars = response.json()["avatars"]
        assert len(avatars) == 1
        assert avatars[0]["id"] == first["id"]
        assert avatars[0]["is_primary"] is True


class TestSetPrimaryCharacterAvatar:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def character(self, db_session, owner, public_sheet, wrap_in_savepoint):
        repository = CharacterRepository(db_session, principal=owner)
        return await repository.create(
            character_sheet_id=public_sheet.id,
            label="Aragorn",
            type=Character.Type.PC,
        )

    @pytest.fixture(autouse=True)
    def _avatars_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path))
        return tmp_path

    async def _add_avatar(self, client, character_id):
        response = await client.post(
            f"/characters/{character_id}/avatar",
            files={"avatar": ("avatar.png", _make_png_bytes(), "image/png")},
        )
        return response.json()["avatar"]

    async def test_requires_auth(self, client, character):
        response = await client.patch(f"/characters/{character.id}/avatar/1")

        assert response.status_code == 403

    async def test_returns_404_when_character_missing(self, authed_client):
        client, _user = authed_client

        response = await client.patch("/characters/999999/avatar/1")

        assert response.status_code == 404

    async def test_returns_404_when_avatar_missing(
        self, client, character, owner, auth_as
    ):
        auth_as(owner)

        response = await client.patch(f"/characters/{character.id}/avatar/999999")

        assert response.status_code == 404

    async def test_forbids_a_non_owner(self, client, character, owner, auth_as, create):
        auth_as(owner)
        avatar = await self._add_avatar(client, character.id)

        stranger = await create(ActivatedUserFactory)
        auth_as(stranger)
        response = await client.patch(
            f"/characters/{character.id}/avatar/{avatar['id']}"
        )

        assert response.status_code == 403

    async def test_makes_the_target_avatar_primary_and_unsets_others(
        self, client, character, owner, auth_as
    ):
        auth_as(owner)
        first = await self._add_avatar(client, character.id)
        second = await self._add_avatar(client, character.id)
        assert first["is_primary"] is True
        assert second["is_primary"] is False

        response = await client.patch(
            f"/characters/{character.id}/avatar/{second['id']}"
        )

        assert response.status_code == 200
        assert response.json()["avatar"]["is_primary"] is True

        get_response = await client.get(f"/characters/{character.id}")
        avatars = {a["id"]: a["is_primary"] for a in get_response.json()["avatars"]}
        assert avatars[first["id"]] is False
        assert avatars[second["id"]] is True


class TestToggleCharacterLibrary:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def character(self, db_session, owner, public_sheet, wrap_in_savepoint):
        repository = CharacterRepository(db_session, principal=owner)
        return await repository.create(
            character_sheet_id=public_sheet.id,
            label="Aragorn",
            type=Character.Type.PC,
        )

    async def test_requires_auth(self, client, character):
        response = await client.patch(f"/characters/{character.id}/toggle_library")

        assert response.status_code == 403

    async def test_returns_404_when_missing(self, authed_client):
        client, _user = authed_client

        response = await client.patch("/characters/999999/toggle_library")

        assert response.status_code == 404

    async def test_forbids_a_non_owner(
        self, client, character, create, auth_as, db_session
    ):
        stranger = await create(ActivatedUserFactory)
        auth_as(stranger)

        response = await client.patch(f"/characters/{character.id}/toggle_library")

        assert response.status_code == 403
        await db_session.refresh(character, ["in_library"])
        assert character.in_library is False

    async def test_toggles_in_and_out_of_the_library(
        self, client, character, owner, auth_as, db_session
    ):
        auth_as(owner)
        assert character.in_library is False

        response = await client.patch(f"/characters/{character.id}/toggle_library")
        assert response.status_code == 204
        await db_session.refresh(character, ["in_library"])
        assert character.in_library is True

        response = await client.patch(f"/characters/{character.id}/toggle_library")
        assert response.status_code == 204
        await db_session.refresh(character, ["in_library"])
        assert character.in_library is False


class TestDeleteCharacter:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def character(self, db_session, owner, public_sheet, wrap_in_savepoint):
        repository = CharacterRepository(db_session, principal=owner)
        character = await repository.create(
            character_sheet_id=public_sheet.id,
            label="Aragorn",
            type=Character.Type.PC,
        )
        character.in_library = True
        await db_session.flush()
        return character

    async def test_requires_auth(self, client, character):
        response = await client.delete(f"/characters/{character.id}")

        assert response.status_code == 403

    async def test_returns_404_when_missing(self, authed_client):
        client, _user = authed_client

        response = await client.delete("/characters/999999")

        assert response.status_code == 404

    async def test_forbids_a_non_owner(
        self, client, character, create, auth_as, db_session
    ):
        stranger = await create(ActivatedUserFactory)
        auth_as(stranger)

        response = await client.delete(f"/characters/{character.id}")

        assert response.status_code == 403
        await db_session.refresh(character, ["deleted"])
        assert character.deleted is None

    async def test_soft_deletes_and_clears_library_and_favorites(
        self, client, character, owner, create, auth_as, db_session
    ):
        other = await create(ActivatedUserFactory)
        db_session.add_all(
            [
                FavoriteCharacter(user_id=owner.id, character_id=character.id),
                FavoriteCharacter(user_id=other.id, character_id=character.id),
            ]
        )
        await db_session.flush()
        auth_as(owner)

        response = await client.delete(f"/characters/{character.id}")

        assert response.status_code == 204
        row = await db_session.scalar(
            select(Character)
            .where(Character.id == character.id)
            .execution_options(skip_filter=True, populate_existing=True)
        )
        assert row is not None
        assert row.deleted is not None
        assert row.in_library is False
        favorites = await db_session.scalars(
            select(FavoriteCharacter).where(
                FavoriteCharacter.character_id == character.id
            )
        )
        assert favorites.all() == []

    async def test_deleted_character_is_no_longer_fetchable(
        self, client, character, owner, auth_as
    ):
        auth_as(owner)
        await client.delete(f"/characters/{character.id}")

        response = await client.get(f"/characters/{character.id}")

        assert response.status_code == 404
