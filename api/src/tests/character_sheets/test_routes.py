import pytest
from sqlalchemy import select
from sqlalchemy.orm import undefer

from app.character_sheets.defaults import default_sheet_layout
from app.models import CharacterSheet
from app.repositories import CharacterSheetRepository
from tests.factories import ActivatedUserFactory, SystemFactory


class TestCreateCharSheet:
    async def test_requires_auth(self, client):
        response = await client.post(
            "/character_sheets/", json={"name": "Fighter", "system_id": "dnd5e"}
        )

        assert response.status_code == 403

    async def test_returns_404_when_system_missing(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/character_sheets/", json={"name": "Fighter", "system_id": "nope"}
        )

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "not_found"

    async def test_creates_sheet_for_authed_user(
        self, authed_client, create, db_session
    ):
        client, user = authed_client
        system = await create(SystemFactory, id="dnd5e")

        response = await client.post(
            "/character_sheets/",
            # Padded name also asserts `name` runs through filtered_str().
            json={"name": "  Fighter  ", "system_id": system.id},
        )

        assert response.status_code == 200
        sheet_id = response.json()["id"]

        sheet = await db_session.scalar(
            select(CharacterSheet)
            .where(CharacterSheet.id == sheet_id)
            .options(undefer(CharacterSheet.layout))
        )
        assert sheet is not None
        assert sheet.creator_id == user.id
        assert sheet.name == "Fighter"
        assert sheet.system_id == system.id
        assert sheet.status == CharacterSheet.Status.PRIVATE
        assert sheet.layout == default_sheet_layout()


class TestGetCharSheet:
    @pytest.fixture
    async def creator(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def sheet(self, creator, create, db_session, wrap_in_savepoint):
        system = await create(SystemFactory, id="dnd5e", name="D&D 5e")
        repository = CharacterSheetRepository(db_session, principal=creator)
        return await repository.create(
            name="Fighter",
            system_id=system.id,
            layout={"version": 1, "elements": [{"type": "header", "text": "Combat"}]},
        )

    async def test_returns_404_when_sheet_missing(self, authed_client):
        client, _user = authed_client

        response = await client.get("/character_sheets/999999")

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "not_found"

    async def test_returns_the_serialized_sheet(self, client, sheet, creator, auth_as):
        auth_as(creator)

        response = await client.get(f"/character_sheets/{sheet.id}")

        assert response.status_code == 200
        assert response.json() == {
            "id": sheet.id,
            "creator": {
                "id": creator.id,
                "username": creator.username,
                "avatar": creator.avatar,
            },
            "root_id": None,
            "name": "Fighter",
            "system": {"id": "dnd5e", "name": "D&D 5e"},
            "layout": {
                "version": 1,
                "elements": [{"type": "header", "text": "Combat"}],
            },
            "status": "private",
        }

    async def test_any_authed_user_can_read_another_users_private_sheet(
        self, client, sheet, create, auth_as
    ):
        # The endpoint has no creator/status gate today; pin that so a future
        # change to it is a deliberate one.
        assert sheet.status == CharacterSheet.Status.PRIVATE
        other = await create(ActivatedUserFactory)
        auth_as(other)

        response = await client.get(f"/character_sheets/{sheet.id}")

        assert response.status_code == 200
        assert response.json()["id"] == sheet.id


class TestUpdateCharSheet:
    @pytest.fixture
    async def creator(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def sheet(self, creator, create, db_session, wrap_in_savepoint):
        system = await create(SystemFactory, id="dnd5e")
        repository = CharacterSheetRepository(db_session, principal=creator)
        return await repository.create(
            name="Fighter", system_id=system.id, layout={"version": 1, "elements": []}
        )

    async def test_requires_auth(self, client, sheet):
        response = await client.patch(
            f"/character_sheets/{sheet.id}", json={"layout": {"elements": []}}
        )

        assert response.status_code == 403

    async def test_returns_404_when_sheet_missing(self, authed_client):
        client, _user = authed_client

        response = await client.patch(
            "/character_sheets/999999", json={"layout": {"elements": []}}
        )

        assert response.status_code == 404

    async def test_forbids_non_creator(self, client, sheet, create, auth_as):
        other = await create(ActivatedUserFactory)
        auth_as(other)

        response = await client.patch(
            f"/character_sheets/{sheet.id}", json={"layout": {"elements": []}}
        )

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "forbidden"

    async def test_creator_saves_the_layout(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)
        new_layout = {
            "version": 1,
            "elements": [{"type": "header", "text": "Combat"}],
        }

        response = await client.patch(
            f"/character_sheets/{sheet.id}", json={"layout": new_layout}
        )

        assert response.status_code == 200
        assert response.json()["layout"] == new_layout

        await db_session.refresh(sheet, ["layout"])
        assert sheet.layout == new_layout

    async def test_rejects_a_layout_off_the_sheet_profile(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"layout": {"version": 1, "elements": [{"type": "bogus"}]}},
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "validation_error"

        await db_session.refresh(sheet, ["layout"])
        assert sheet.layout == {"version": 1, "elements": []}
