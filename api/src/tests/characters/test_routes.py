import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.characters.schemas import MAX_VALUES_SIZE
from app.configs import configs
from app.models import (
    Character,
    CharacterFavorite,
    CharacterSheet,
    FavoriteCharacter,
    UserMeta,
)
from app.repositories import CharacterRepository, CharacterSheetRepository
from tests.factories import ActivatedUserFactory, SystemFactory

SHEET_LAYOUT = {
    "schema_version": 1,
    "elements": [
        {"type": "header", "text": "Combat"},
        {"type": "input", "name": "str", "id": "str1"},
        {
            "type": "grid",
            "name": "skills",
            "id": "skl1",
            "items": [{"key": "stealth", "label": "Stealth", "id": "stl1"}],
            "row": [{"type": "input", "name": "rank", "id": "rnk1"}],
        },
    ],
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
    await repository.publish(await repository.get_draft(sheet.id))
    sheet.status = status
    await db_session.flush()
    return sheet


async def _create_character(db_session, owner, sheet, label, **kwargs):
    """Create a character pinned to the sheet's latest published version."""
    version = await CharacterSheetRepository(
        db_session, principal=owner
    ).get_latest_published(sheet.id)
    return await CharacterRepository(db_session, principal=owner).create(
        character_sheet_id=sheet.id,
        character_sheet_version_id=version.id,
        label=label,
        **kwargs,
    )


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

    async def test_reports_a_missing_field_in_the_errors_shape(self, authed_client):
        client, _user = authed_client

        response = await client.post("/characters/", json={"label": "Aragorn"})

        assert response.status_code == 422
        assert response.json()["errors"] == [
            {
                "field": "character_sheet_id",
                "code": "validation_error",
                "detail": "Field required",
            }
        ]

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

    async def test_pins_the_latest_published_version(
        self, client, public_sheet, sheet_creator, create, auth_as, db_session
    ):
        repository = CharacterSheetRepository(db_session, principal=sheet_creator)
        draft = await repository.save_draft(
            public_sheet, layout={"schema_version": 1, "elements": []}
        )
        newer = await repository.publish(draft)
        user = await create(ActivatedUserFactory)
        auth_as(user)

        response = await client.post(
            "/characters/",
            json={"label": "Aragorn", "character_sheet_id": public_sheet.id},
        )

        assert response.status_code == 200
        character = await db_session.get(Character, response.json()["id"])
        assert newer.number == 2
        assert character.character_sheet_version_id == newer.id

    async def test_rejects_a_sheet_with_no_published_version(
        self, client, sheet_creator, system, auth_as, db_session
    ):
        repository = CharacterSheetRepository(db_session, principal=sheet_creator)
        sheet = await repository.create(name="Wip", system_id=system.id)
        auth_as(sheet_creator)

        response = await client.post(
            "/characters/", json={"label": "Aragorn", "character_sheet_id": sheet.id}
        )

        assert response.status_code == 409

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
        return await _create_character(db_session, owner, public_sheet, "Aragorn")

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
            "character_sheet_id": public_sheet.id,
            "character_sheet": {
                "id": public_sheet.id,
                "name": "Fighter",
                "creator": {
                    "id": sheet_creator.id,
                    "username": sheet_creator.username,
                    "avatar": sheet_creator.avatar,
                },
                "system": {"id": "dnd5e", "name": "D&D 5e"},
            },
            "sheet_deleted": False,
            "version_id": character.character_sheet_version_id,
            "version_number": 1,
            "layout": SHEET_LAYOUT,
            "avatars": [],
        }

    async def test_loads_the_sheet_creators_avatar_when_they_arent_the_viewer(
        self, client, character, owner, sheet_creator, db_session, auth_as
    ):
        # A real request starts with only the viewer loaded; here the creator
        # would otherwise sit in the session with `meta` already filled.
        # A set avatar, so the response can't match by falling back to the default.
        sheet_creator.meta.append(
            UserMeta(key=UserMeta.MetaKeys.AVATAR_EXT.value, value="jpg")
        )
        await db_session.flush()
        # Read everything needed before expiring: an expired attribute can't
        # lazy-load outside the async session.
        character_id = character.id
        sheet_creator_id = sheet_creator.id
        auth_as(owner)
        db_session.expire_all()

        response = await client.get(f"/characters/{character_id}")

        assert response.status_code == 200
        assert (
            response.json()["character_sheet"]["creator"]["avatar"]
            == f"{sheet_creator_id}.jpg"
        )

    async def test_serves_the_pinned_layout_after_the_sheet_changes(
        self, client, character, owner, sheet_creator, public_sheet, db_session, auth_as
    ):
        repository = CharacterSheetRepository(db_session, principal=sheet_creator)
        draft = await repository.save_draft(
            public_sheet, layout={"schema_version": 1, "elements": []}
        )
        await repository.publish(draft)
        auth_as(owner)

        response = await client.get(f"/characters/{character.id}")

        assert response.json()["layout"] == SHEET_LAYOUT

    async def test_a_deleted_sheet_leaves_the_character_readable(
        self, client, character, owner, sheet_creator, public_sheet, db_session, auth_as
    ):
        await CharacterSheetRepository(db_session, principal=sheet_creator).delete(
            public_sheet
        )
        auth_as(owner)

        response = await client.get(f"/characters/{character.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["sheet_deleted"] is True
        # The sheet's details stay, so the character keeps its system.
        assert body["character_sheet"]["id"] == public_sheet.id
        assert body["character_sheet"]["system"] == {"id": "dnd5e", "name": "D&D 5e"}
        assert body["layout"] == SHEET_LAYOUT

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
        return await _create_character(db_session, owner, sheet, label, type=type)

    async def test_requires_auth(self, client):
        response = await client.get("/characters")

        assert response.status_code == 403

    async def test_only_returns_the_principals_characters(
        self,
        client,
        public_sheet,
        owner,
        create,
        auth_as,
        db_session,
        wrap_in_savepoint,
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

    async def test_list_items_leave_out_the_layout_and_values(
        self, client, public_sheet, owner, auth_as, db_session, wrap_in_savepoint
    ):
        character = await self._make_character(
            db_session, owner, public_sheet, "Aragorn"
        )
        character.values = {"str": 18}
        await db_session.flush()
        auth_as(owner)

        response = await client.get("/characters")

        assert response.json()["characters"] == [
            {
                "id": character.id,
                "label": "Aragorn",
                "type": "pc",
                "in_library": False,
                "user": {"id": owner.id, "username": owner.username},
                "character_sheet_id": public_sheet.id,
                "character_sheet": {
                    "id": public_sheet.id,
                    "name": "Fighter",
                    "system": {"id": "dnd5e", "name": "D&D 5e"},
                },
                "sheet_deleted": False,
            }
        ]

    async def test_a_deleted_sheet_keeps_its_characters_system(
        self,
        client,
        public_sheet,
        sheet_creator,
        owner,
        system,
        create,
        auth_as,
        db_session,
        wrap_in_savepoint,
    ):
        other_system = await create(SystemFactory, id="pf2e", sort_name="ZZZ System")
        gone = await _make_sheet(
            db_session,
            sheet_creator,
            system,
            status=CharacterSheet.Status.PUBLIC,
        )
        other_sheet = await _make_sheet(
            db_session,
            sheet_creator,
            other_system,
            status=CharacterSheet.Status.PUBLIC,
        )
        await self._make_character(db_session, owner, gone, "Zed")
        await self._make_character(db_session, owner, public_sheet, "Aaron")
        await self._make_character(db_session, owner, other_sheet, "Bob")
        await CharacterSheetRepository(db_session, principal=sheet_creator).delete(gone)
        auth_as(owner)

        response = await client.get("/characters")

        body = response.json()
        # Sorted by its system like any other character, not pushed to the end.
        assert [c["label"] for c in body["characters"]] == ["Aaron", "Zed", "Bob"]
        assert body["characters"][1]["sheet_deleted"] is True
        assert body["characters"][1]["character_sheet"]["system"]["id"] == "dnd5e"

        filtered = await client.get("/characters", params={"system_id": "dnd5e"})

        assert filtered.json()["total"] == 2
        assert [c["label"] for c in filtered.json()["characters"]] == ["Aaron", "Zed"]

    async def test_leaves_out_deleted_characters(
        self, client, public_sheet, owner, auth_as, db_session, wrap_in_savepoint
    ):
        gone = await self._make_character(db_session, owner, public_sheet, "Boromir")
        await self._make_character(db_session, owner, public_sheet, "Aragorn")
        await CharacterRepository(db_session, principal=owner).delete(gone)
        auth_as(owner)

        response = await client.get("/characters")

        body = response.json()
        assert body["total"] == 1
        assert [c["label"] for c in body["characters"]] == ["Aragorn"]

    async def test_orders_by_system_then_label(
        self,
        client,
        owner,
        sheet_creator,
        create,
        auth_as,
        db_session,
        wrap_in_savepoint,
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
        self,
        client,
        owner,
        sheet_creator,
        create,
        auth_as,
        db_session,
        wrap_in_savepoint,
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
            await self._make_character(db_session, owner, public_sheet, f"Char {i:03}")
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

    async def test_includes_favorited_library_characters_with_their_owner(
        self,
        client,
        public_sheet,
        owner,
        create,
        auth_as,
        db_session,
        wrap_in_savepoint,
    ):
        stranger = await create(ActivatedUserFactory)
        favorited = await self._make_character(
            db_session, stranger, public_sheet, "Legolas"
        )
        favorited.in_library = True
        await self._make_character(db_session, stranger, public_sheet, "Gimli")
        await self._make_character(db_session, owner, public_sheet, "Aragorn")
        db_session.add(CharacterFavorite(user_id=owner.id, character_id=favorited.id))
        await db_session.flush()
        auth_as(owner)

        response = await client.get("/characters")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        users = {c["label"]: c["user"] for c in body["characters"]}
        assert users == {
            "Aragorn": {"id": owner.id, "username": owner.username},
            "Legolas": {"id": stranger.id, "username": stranger.username},
        }

    async def test_excludes_favorites_no_longer_in_the_library(
        self,
        client,
        public_sheet,
        owner,
        create,
        auth_as,
        db_session,
        wrap_in_savepoint,
    ):
        stranger = await create(ActivatedUserFactory)
        delisted = await self._make_character(
            db_session, stranger, public_sheet, "Legolas"
        )
        db_session.add(CharacterFavorite(user_id=owner.id, character_id=delisted.id))
        await db_session.flush()
        auth_as(owner)

        response = await client.get("/characters")

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_repository_omits_favorites_unless_asked(
        self, public_sheet, owner, create, db_session, wrap_in_savepoint
    ):
        stranger = await create(ActivatedUserFactory)
        favorited = await self._make_character(
            db_session, stranger, public_sheet, "Legolas"
        )
        favorited.in_library = True
        db_session.add(CharacterFavorite(user_id=owner.id, character_id=favorited.id))
        await db_session.flush()
        repository = CharacterRepository(db_session, principal=owner)

        assert list(await repository.get_all()) == []
        assert await repository.count_all() == 0
        assert len(list(await repository.get_all(include_favorited=True))) == 1
        assert await repository.count_all(include_favorited=True) == 1


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
        character = await _create_character(db_session, owner, sheet, label, type=type)
        character.in_library = in_library
        await db_session.flush()
        return character

    async def test_requires_auth(self, client):
        response = await client.get("/characters/library")

        assert response.status_code == 403

    async def test_excludes_characters_whose_sheet_was_deleted(
        self,
        client,
        public_sheet,
        sheet_creator,
        owner,
        viewer,
        auth_as,
        db_session,
        wrap_in_savepoint,
    ):
        await self._make_character(db_session, owner, public_sheet, "Aragorn")
        await CharacterSheetRepository(db_session, principal=sheet_creator).delete(
            public_sheet
        )
        auth_as(viewer)

        response = await client.get("/characters/library")

        assert response.status_code == 200
        assert response.json()["total"] == 0
        assert response.json()["characters"] == []

    async def test_returns_only_id_label_system_user_and_favorited(
        self,
        client,
        public_sheet,
        owner,
        viewer,
        auth_as,
        db_session,
        wrap_in_savepoint,
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
                "favorited": False,
            }
        ]

    async def test_marks_only_characters_favorited_by_the_viewer(
        self,
        client,
        public_sheet,
        owner,
        viewer,
        auth_as,
        db_session,
        wrap_in_savepoint,
    ):
        liked = await self._make_character(db_session, owner, public_sheet, "Liked")
        await self._make_character(db_session, owner, public_sheet, "Plain")
        db_session.add(CharacterFavorite(user_id=viewer.id, character_id=liked.id))
        await db_session.flush()
        auth_as(viewer)

        response = await client.get("/characters/library")

        body = response.json()
        assert body["total"] == 2
        assert {c["label"]: c["favorited"] for c in body["characters"]} == {
            "Liked": True,
            "Plain": False,
        }

    async def test_ignores_favorites_from_other_users(
        self,
        client,
        public_sheet,
        owner,
        viewer,
        create,
        auth_as,
        db_session,
        wrap_in_savepoint,
    ):
        others = [await create(ActivatedUserFactory) for _ in range(2)]
        character = await self._make_character(
            db_session, owner, public_sheet, "Aragorn"
        )
        for other in others:
            db_session.add(
                CharacterFavorite(user_id=other.id, character_id=character.id)
            )
        await db_session.flush()
        auth_as(viewer)

        response = await client.get("/characters/library")

        body = response.json()
        assert body["total"] == 1
        assert [c["favorited"] for c in body["characters"]] == [False]

    async def test_returns_one_row_when_viewer_and_others_favorited(
        self,
        client,
        public_sheet,
        owner,
        viewer,
        create,
        auth_as,
        db_session,
        wrap_in_savepoint,
    ):
        other = await create(ActivatedUserFactory)
        character = await self._make_character(
            db_session, owner, public_sheet, "Aragorn"
        )
        for user in (viewer, other):
            db_session.add(
                CharacterFavorite(user_id=user.id, character_id=character.id)
            )
        await db_session.flush()
        auth_as(viewer)

        response = await client.get("/characters/library")

        body = response.json()
        # A join on character_id alone would return one row per favoriting user.
        assert body["total"] == 1
        assert [c["favorited"] for c in body["characters"]] == [True]

    async def test_excludes_own_and_non_library_characters(
        self,
        client,
        public_sheet,
        owner,
        viewer,
        auth_as,
        db_session,
        wrap_in_savepoint,
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
        self,
        client,
        owner,
        viewer,
        sheet_creator,
        create,
        auth_as,
        db_session,
        wrap_in_savepoint,
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
        self,
        client,
        public_sheet,
        owner,
        viewer,
        auth_as,
        db_session,
        wrap_in_savepoint,
    ):
        await self._make_character(db_session, owner, public_sheet, "Aragorn")
        await self._make_character(db_session, owner, public_sheet, "Legolas")
        auth_as(viewer)

        response = await client.get("/characters/library", params={"search": "arag"})

        body = response.json()
        assert body["total"] == 1
        assert [c["label"] for c in body["characters"]] == ["Aragorn"]

    async def test_filters_by_type(
        self,
        client,
        public_sheet,
        owner,
        viewer,
        auth_as,
        db_session,
        wrap_in_savepoint,
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
        self,
        client,
        owner,
        viewer,
        sheet_creator,
        create,
        auth_as,
        db_session,
        wrap_in_savepoint,
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
        self,
        client,
        public_sheet,
        owner,
        viewer,
        auth_as,
        db_session,
        wrap_in_savepoint,
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
        self,
        client,
        public_sheet,
        owner,
        viewer,
        auth_as,
        db_session,
        wrap_in_savepoint,
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
        return await _create_character(db_session, owner, public_sheet, "Aragorn")

    async def test_requires_auth(self, client, character):
        response = await client.patch(
            f"/characters/{character.id}", json={"values": {"str1": 18}}
        )

        assert response.status_code == 403

    async def test_returns_404_when_missing(self, authed_client):
        client, _user = authed_client

        response = await client.patch(
            "/characters/999999", json={"values": {"str1": 18}}
        )

        assert response.status_code == 404

    async def test_forbids_a_non_owner(self, client, character, create, auth_as):
        stranger = await create(ActivatedUserFactory)
        auth_as(stranger)

        response = await client.patch(
            f"/characters/{character.id}", json={"values": {"str1": 18}}
        )

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "forbidden"

    async def test_owner_saves_the_values(
        self, client, character, owner, public_sheet, db_session, auth_as
    ):
        auth_as(owner)
        new_values = {"str1": 18, "skl1": {"stl1": {"rnk1": 3}}}

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
        await client.patch(f"/characters/{character.id}", json={"values": {"str1": 18}})

        response = await client.patch(
            f"/characters/{character.id}", json={"label": "Strider"}
        )

        assert response.status_code == 200
        assert response.json()["label"] == "Strider"
        assert response.json()["type"] == "pc"
        assert response.json()["values"] == {"str1": 18}

    async def test_rejects_values_over_the_size_cap(
        self, client, character, owner, db_session, auth_as
    ):
        auth_as(owner)

        response = await client.patch(
            f"/characters/{character.id}",
            json={"values": {"notes": "x" * MAX_VALUES_SIZE}},
        )

        assert response.status_code == 422
        assert response.json()["errors"] == [
            {
                "field": "values",
                "code": "validation_error",
                "detail": "Character values can't exceed 512 KB",
            }
        ]
        await db_session.refresh(character, ["values"])
        assert character.values is None

    async def test_a_body_level_422_has_no_field(
        self, client, character, owner, auth_as
    ):
        auth_as(owner)

        # Not an object, so the error is about the body itself: its location
        # is just "body", which leaves nothing to name as the field.
        response = await client.patch(f"/characters/{character.id}", json=["label"])

        assert response.status_code == 422
        [error] = response.json()["errors"]
        assert "field" not in error
        assert error["code"] == "validation_error"

    async def test_rejects_values_the_sheet_doesnt_define(
        self, client, character, owner, db_session, auth_as
    ):
        auth_as(owner)

        response = await client.patch(
            f"/characters/{character.id}", json={"values": {"nope": 1}}
        )

        assert response.status_code == 400
        error = response.json()["errors"][0]
        assert error["code"] == "validation_error"
        assert "'nope'" in error["detail"]
        await db_session.refresh(character, ["values"])
        assert character.values is None

    async def test_keeps_values_for_fields_the_sheet_no_longer_has(
        self, client, character, owner, db_session, auth_as
    ):
        character.values = {"old1": "from an earlier version"}
        await db_session.flush()
        auth_as(owner)
        new_values = {"old1": "from an earlier version", "str1": 18}

        response = await client.patch(
            f"/characters/{character.id}", json={"values": new_values}
        )

        assert response.status_code == 200
        assert response.json()["values"] == new_values


class TestAddCharacterAvatar:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def character(self, db_session, owner, public_sheet, wrap_in_savepoint):
        return await _create_character(db_session, owner, public_sheet, "Aragorn")

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
        return await _create_character(db_session, owner, public_sheet, "Aragorn")

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
        return await _create_character(db_session, owner, public_sheet, "Aragorn")

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
        return await _create_character(db_session, owner, public_sheet, "Aragorn")

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


class TestToggleCharacterFavorite:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def viewer(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def character(self, db_session, owner, public_sheet, wrap_in_savepoint):
        return await _create_character(db_session, owner, public_sheet, "Aragorn")

    async def _favorite_user_ids(self, db_session, character):
        rows = await db_session.scalars(
            select(CharacterFavorite.user_id).where(
                CharacterFavorite.character_id == character.id
            )
        )
        return set(rows)

    async def test_requires_auth(self, client, character):
        response = await client.patch(f"/characters/{character.id}/toggle_favorite")

        assert response.status_code == 403

    async def test_returns_404_when_missing(self, authed_client):
        client, _user = authed_client

        response = await client.patch("/characters/999999/toggle_favorite")

        assert response.status_code == 404

    async def test_forbids_favoriting_a_private_character_of_another_user(
        self, client, character, viewer, auth_as, db_session
    ):
        auth_as(viewer)

        response = await client.patch(f"/characters/{character.id}/toggle_favorite")

        assert response.status_code == 403
        assert await self._favorite_user_ids(db_session, character) == set()

    async def test_owner_can_favorite_their_own_private_character(
        self, client, character, owner, auth_as, db_session
    ):
        auth_as(owner)

        response = await client.patch(f"/characters/{character.id}/toggle_favorite")

        assert response.status_code == 200
        assert response.json() == {"favorited": True}
        assert await self._favorite_user_ids(db_session, character) == {owner.id}

    async def test_toggles_on_and_off_for_a_library_character(
        self, client, character, viewer, auth_as, db_session
    ):
        character.in_library = True
        await db_session.flush()
        auth_as(viewer)

        response = await client.patch(f"/characters/{character.id}/toggle_favorite")
        assert response.status_code == 200
        assert response.json() == {"favorited": True}
        assert await self._favorite_user_ids(db_session, character) == {viewer.id}

        response = await client.patch(f"/characters/{character.id}/toggle_favorite")
        assert response.status_code == 200
        assert response.json() == {"favorited": False}
        assert await self._favorite_user_ids(db_session, character) == set()

    async def test_only_toggles_the_current_users_favorite(
        self, client, character, owner, viewer, auth_as, db_session
    ):
        character.in_library = True
        db_session.add(CharacterFavorite(user_id=owner.id, character_id=character.id))
        await db_session.flush()
        auth_as(viewer)

        response = await client.patch(f"/characters/{character.id}/toggle_favorite")

        assert response.json() == {"favorited": True}
        assert await self._favorite_user_ids(db_session, character) == {
            owner.id,
            viewer.id,
        }

    async def test_favorite_shows_up_in_the_library(
        self, client, character, viewer, auth_as, db_session
    ):
        character.in_library = True
        await db_session.flush()
        auth_as(viewer)

        await client.patch(f"/characters/{character.id}/toggle_favorite")
        response = await client.get("/characters/library")

        assert [c["favorited"] for c in response.json()["characters"]] == [True]


class TestDeleteCharacter:
    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def character(self, db_session, owner, public_sheet, wrap_in_savepoint):
        character = await _create_character(db_session, owner, public_sheet, "Aragorn")
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
                CharacterFavorite(user_id=owner.id, character_id=character.id),
                CharacterFavorite(user_id=other.id, character_id=character.id),
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
        character_favorites = await db_session.scalars(
            select(CharacterFavorite).where(
                CharacterFavorite.character_id == character.id
            )
        )
        assert character_favorites.all() == []

    async def test_deleted_character_is_no_longer_fetchable(
        self, client, character, owner, auth_as
    ):
        auth_as(owner)
        await client.delete(f"/characters/{character.id}")

        response = await client.get(f"/characters/{character.id}")

        assert response.status_code == 404


# `SHEET_LAYOUT` without the skills grid, then with a field added back.
SHEET_LAYOUT_V2 = {**SHEET_LAYOUT, "elements": SHEET_LAYOUT["elements"][:2]}
SHEET_LAYOUT_V3 = {
    **SHEET_LAYOUT,
    "elements": [*SHEET_LAYOUT_V2["elements"], {"type": "input", "name": "dex"}],
}


class TestCharacterSheetMoves:
    """Upgrading (a newer version of the character's sheet) and changing (a
    version of a copy of it)."""

    @pytest.fixture
    async def owner(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def copier(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def character(self, db_session, owner, sheet_creator, public_sheet):
        """On v1 of `public_sheet`, which has since published v2 and v3."""
        character = await _create_character(db_session, owner, public_sheet, "Arya")
        await self._publish(db_session, sheet_creator, public_sheet, SHEET_LAYOUT_V2)
        await self._publish(db_session, sheet_creator, public_sheet, SHEET_LAYOUT_V3)
        return character

    async def _publish(self, db_session, user, sheet, layout):
        repository = CharacterSheetRepository(db_session, principal=user)
        return await repository.publish(
            await repository.save_draft(sheet, layout=layout)
        )

    async def _copy(
        self,
        db_session,
        user,
        sheet,
        *,
        status=CharacterSheet.Status.PUBLIC,
        publish=True,
    ):
        repository = CharacterSheetRepository(db_session, principal=user)
        version = await repository.get_latest_published(sheet.id)
        copied = await repository.create_copy(sheet, version, publish=publish)
        copied.status = status
        await db_session.flush()
        return copied

    async def _pinned(self, db_session, character):
        return await db_session.scalar(
            select(Character)
            .where(Character.id == character.id)
            .execution_options(populate_existing=True)
        )

    async def test_options_are_owner_only(self, client, character, copier, auth_as):
        auth_as(copier)

        response = await client.get(f"/characters/{character.id}/sheet_moves")

        assert response.status_code == 403

    async def test_options_list_newer_versions_newest_first(
        self, client, character, owner, auth_as
    ):
        auth_as(owner)

        response = await client.get(f"/characters/{character.id}/sheet_moves")

        assert response.status_code == 200
        assert [v["number"] for v in response.json()["versions"]] == [3, 2]
        assert response.json()["copies"] == []

    async def test_options_list_visible_published_copies_at_any_depth(
        self, client, character, owner, copier, public_sheet, db_session, auth_as
    ):
        public_copy = await self._copy(db_session, copier, public_sheet)
        deleted_copy = await self._copy(db_session, copier, public_sheet)
        copy_of_deleted = await self._copy(db_session, copier, deleted_copy)
        await CharacterSheetRepository(db_session, principal=copier).delete(
            deleted_copy
        )
        own_private_copy = await self._copy(
            db_session, owner, public_sheet, status=CharacterSheet.Status.PRIVATE
        )
        await self._copy(
            db_session, copier, public_sheet, status=CharacterSheet.Status.PRIVATE
        )
        await self._copy(db_session, copier, public_sheet, publish=False)
        auth_as(owner)

        response = await client.get(f"/characters/{character.id}/sheet_moves")

        assert response.status_code == 200
        # By name: the copy of a copy is "Fighter (Copy) (Copy)".
        assert [c["id"] for c in response.json()["copies"]] == [
            public_copy.id,
            own_private_copy.id,
            copy_of_deleted.id,
        ]

    async def test_a_deleted_sheet_offers_only_its_copies(
        self,
        client,
        character,
        owner,
        copier,
        sheet_creator,
        public_sheet,
        db_session,
        auth_as,
    ):
        public_copy = await self._copy(db_session, copier, public_sheet)
        await CharacterSheetRepository(db_session, principal=sheet_creator).delete(
            public_sheet
        )
        auth_as(owner)

        response = await client.get(f"/characters/{character.id}/sheet_moves")

        assert response.status_code == 200
        assert response.json()["versions"] == []
        assert [c["id"] for c in response.json()["copies"]] == [public_copy.id]

    async def test_preview_shows_the_target_layout_and_hidden_values(
        self, client, character, owner, public_sheet, db_session, auth_as
    ):
        character.values = {"str1": "16", "skl1": {"stl1": {"rnk1": "2"}}}
        await db_session.flush()
        v2 = await CharacterSheetRepository(db_session, principal=owner).get_published(
            public_sheet.id, 2
        )
        auth_as(owner)

        response = await client.get(
            f"/characters/{character.id}/sheet_moves/preview",
            params={"character_sheet_id": public_sheet.id, "version": 2},
        )

        assert response.status_code == 200
        assert response.json() == {
            "name": "Fighter",
            "layout": v2.layout,
            "hidden_values": [{"id": "skl1", "label": "skills"}],
        }

    async def test_upgrades_keeping_values(
        self, client, character, owner, public_sheet, db_session, auth_as
    ):
        character.values = {"str1": "16", "skl1": {"stl1": {"rnk1": "2"}}}
        await db_session.flush()
        auth_as(owner)

        response = await client.post(
            "/characters/sheet_moves",
            json={
                "character_ids": [character.id],
                "character_sheet_id": public_sheet.id,
                "version": 2,
            },
        )

        assert response.status_code == 204
        moved = await self._pinned(db_session, character)
        version = await CharacterSheetRepository(
            db_session, principal=owner
        ).get_version(moved.character_sheet_version_id)
        assert version.number == 2
        # The grid's values stay, though v2 dropped the grid.
        assert moved.values == {"str1": "16", "skl1": {"stl1": {"rnk1": "2"}}}

    async def test_changes_to_a_copy(
        self, client, character, owner, copier, public_sheet, db_session, auth_as
    ):
        public_copy = await self._copy(db_session, copier, public_sheet)
        auth_as(owner)

        response = await client.post(
            "/characters/sheet_moves",
            json={
                "character_ids": [character.id],
                "character_sheet_id": public_copy.id,
                "version": 1,
            },
        )

        assert response.status_code == 204
        moved = await self._pinned(db_session, character)
        assert moved.character_sheet_id == public_copy.id

    async def test_rejects_a_version_that_isnt_newer(
        self, client, character, owner, public_sheet, auth_as
    ):
        auth_as(owner)

        response = await client.post(
            "/characters/sheet_moves",
            json={
                "character_ids": [character.id],
                "character_sheet_id": public_sheet.id,
                "version": 1,
            },
        )

        assert response.status_code == 400

    async def test_rejects_moving_back_to_the_sheet_a_copy_came_from(
        self, client, owner, copier, public_sheet, db_session, auth_as
    ):
        public_copy = await self._copy(db_session, copier, public_sheet)
        on_copy = await _create_character(db_session, owner, public_copy, "Sansa")
        auth_as(owner)

        response = await client.post(
            "/characters/sheet_moves",
            json={
                "character_ids": [on_copy.id],
                "character_sheet_id": public_sheet.id,
                "version": 1,
            },
        )

        assert response.status_code == 400

    async def test_returns_404_for_a_deleted_target(
        self, client, character, owner, copier, public_sheet, db_session, auth_as
    ):
        public_copy = await self._copy(db_session, copier, public_sheet)
        await CharacterSheetRepository(db_session, principal=copier).delete(public_copy)
        auth_as(owner)

        response = await client.post(
            "/characters/sheet_moves",
            json={
                "character_ids": [character.id],
                "character_sheet_id": public_copy.id,
                "version": 1,
            },
        )

        assert response.status_code == 404

    async def test_returns_404_for_an_unpublished_version(
        self, client, character, owner, public_sheet, auth_as
    ):
        auth_as(owner)

        response = await client.post(
            "/characters/sheet_moves",
            json={
                "character_ids": [character.id],
                "character_sheet_id": public_sheet.id,
                "version": 4,
            },
        )

        assert response.status_code == 404

    async def test_returns_404_for_an_unknown_character(
        self, client, character, owner, public_sheet, auth_as
    ):
        auth_as(owner)

        response = await client.post(
            "/characters/sheet_moves",
            json={
                "character_ids": [character.id, 999999],
                "character_sheet_id": public_sheet.id,
                "version": 2,
            },
        )

        assert response.status_code == 404

    async def test_forbids_another_users_private_copy(
        self, client, character, owner, copier, public_sheet, db_session, auth_as
    ):
        private_copy = await self._copy(
            db_session, copier, public_sheet, status=CharacterSheet.Status.PRIVATE
        )
        auth_as(owner)

        response = await client.post(
            "/characters/sheet_moves",
            json={
                "character_ids": [character.id],
                "character_sheet_id": private_copy.id,
                "version": 1,
            },
        )

        assert response.status_code == 403

    async def test_forbids_moving_another_users_character(
        self, client, character, copier, public_sheet, auth_as
    ):
        auth_as(copier)

        response = await client.post(
            "/characters/sheet_moves",
            json={
                "character_ids": [character.id],
                "character_sheet_id": public_sheet.id,
                "version": 2,
            },
        )

        assert response.status_code == 403

    async def test_moves_every_character_or_none(
        self, client, character, owner, public_sheet, db_session, auth_as
    ):
        on_v3 = await _create_character(db_session, owner, public_sheet, "Bran")
        v1_id = character.character_sheet_version_id
        auth_as(owner)

        response = await client.post(
            "/characters/sheet_moves",
            json={
                "character_ids": [character.id, on_v3.id],
                "character_sheet_id": public_sheet.id,
                "version": 2,
            },
        )

        assert response.status_code == 400
        unmoved = await self._pinned(db_session, character)
        assert unmoved.character_sheet_version_id == v1_id
