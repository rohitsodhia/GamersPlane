from sqlalchemy import select

from app.models import CharacterSheet
from tests.factories import SystemFactory


class TestCreateCharSheet:
    async def test_requires_auth(self, client):
        response = await client.post(
            "/character_sheets/", json={"label": "Fighter", "system_id": "dnd5e"}
        )

        assert response.status_code == 403

    async def test_returns_404_when_system_missing(self, authed_client):
        client, _user = authed_client

        response = await client.post(
            "/character_sheets/", json={"label": "Fighter", "system_id": "nope"}
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
            # Padded label also asserts `label` runs through filtered_str().
            json={"label": "  Fighter  ", "system_id": system.id},
        )

        assert response.status_code == 200
        sheet_id = response.json()["id"]

        sheet = await db_session.scalar(
            select(CharacterSheet).where(CharacterSheet.id == sheet_id)
        )
        assert sheet is not None
        assert sheet.creator_id == user.id
        assert sheet.label == "Fighter"
        assert sheet.system_id == system.id
        assert sheet.status == CharacterSheet.Status.PRIVATE
