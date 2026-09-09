import pytest

from app.models import Character, CharacterSheet
from app.repositories import CharacterRepository, CharacterSheetRepository
from tests.factories import ActivatedUserFactory, SystemFactory

SHEET_LAYOUT = {
    "schema_version": 1,
    "elements": [{"type": "header", "text": "Combat"}],
}


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
            "label": "Aragorn",
            "name": None,
            "type": "pc",
            "values": None,
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
        }

    async def test_any_authed_user_can_read_another_users_character(
        self, client, character, create, auth_as
    ):
        # The endpoint has no owner gate today; pin that so a future change
        # to it is a deliberate one.
        stranger = await create(ActivatedUserFactory)
        auth_as(stranger)

        response = await client.get(f"/characters/{character.id}")

        assert response.status_code == 200
        assert response.json()["id"] == character.id


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
