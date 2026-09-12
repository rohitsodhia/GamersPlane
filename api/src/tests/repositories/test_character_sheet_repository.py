import pytest
from sqlalchemy import select

from app.character_sheets.defaults import default_sheet_layout
from app.models import CharacterSheet
from app.repositories import CharacterSheetRepository
from tests.factories import ActivatedUserFactory, SystemFactory


class TestCreate:
    @pytest.fixture
    async def principal(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e")

    @pytest.fixture
    async def repository(self, db_session, principal, wrap_in_savepoint):
        return CharacterSheetRepository(db_session, principal=principal)

    async def test_create_returns_persisted_sheet(
        self, repository, db_session, principal, system
    ):
        sheet = await repository.create(name="Fighter", system_id=system.id)

        assert sheet.id is not None
        assert sheet.creator_id == principal.id
        assert sheet.name == "Fighter"
        assert sheet.system_id == system.id

        stored = await db_session.scalar(
            select(CharacterSheet).where(CharacterSheet.id == sheet.id)
        )
        assert stored is sheet

    async def test_create_stores_the_given_layout(self, repository, system):
        layout = {"version": 1, "elements": [{"type": "section", "content": []}]}

        sheet = await repository.create(
            name="Fighter", system_id=system.id, layout=layout
        )

        assert sheet.layout == layout

    async def test_create_falls_back_to_the_default_layout(self, repository, system):
        sheet = await repository.create(name="Fighter", system_id=system.id)

        assert sheet.layout == default_sheet_layout()
