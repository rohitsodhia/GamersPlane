import pytest
from sqlalchemy import select

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
        sheet = await repository.create(label="Fighter", system_id=system.id)

        assert sheet.id is not None
        assert sheet.creator_id == principal.id
        assert sheet.label == "Fighter"
        assert sheet.system_id == system.id

        stored = await db_session.scalar(
            select(CharacterSheet).where(CharacterSheet.id == sheet.id)
        )
        assert stored is sheet
