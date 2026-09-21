import pytest
from sqlalchemy import select

from app.character_sheets.defaults import default_sheet_layout
from app.character_sheets.layout_validation import SCHEMA_VERSION
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

    async def test_create_stores_the_given_layout_in_a_draft(self, repository, system):
        layout = {"version": 1, "elements": [{"type": "section", "content": []}]}

        sheet = await repository.create(
            name="Fighter", system_id=system.id, layout=layout
        )

        draft = await repository.get_draft(sheet.id)
        assert draft.layout == layout
        assert draft.is_draft
        assert draft.number is None
        assert draft.schema_version == SCHEMA_VERSION

    async def test_create_falls_back_to_the_default_layout(self, repository, system):
        sheet = await repository.create(name="Fighter", system_id=system.id)

        assert (await repository.get_draft(sheet.id)).layout == default_sheet_layout()


class TestVersions:
    @pytest.fixture
    async def principal(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def repository(self, db_session, principal, wrap_in_savepoint):
        return CharacterSheetRepository(db_session, principal=principal)

    @pytest.fixture
    async def sheet(self, repository, create):
        system = await create(SystemFactory, id="dnd5e")
        return await repository.create(
            name="Fighter", system_id=system.id, layout={"elements": ["v1"]}
        )

    async def test_publish_numbers_versions_sequentially(self, repository, sheet):
        first = await repository.publish(
            await repository.get_draft(sheet.id), changelog="first"
        )
        second = await repository.publish(await repository.get_or_create_draft(sheet))

        assert (first.number, second.number) == (1, 2)
        assert first.changelog == "first"
        assert first.published_at is not None
        assert not first.is_draft

    async def test_get_latest_published_ignores_the_draft(self, repository, sheet):
        assert await repository.get_latest_published(sheet.id) is None

        published = await repository.publish(await repository.get_draft(sheet.id))
        await repository.get_or_create_draft(sheet)

        assert (await repository.get_latest_published(sheet.id)).id == published.id

    async def test_get_or_create_draft_copies_the_latest_published_layout(
        self, repository, sheet
    ):
        published = await repository.publish(await repository.get_draft(sheet.id))

        draft = await repository.get_or_create_draft(sheet)

        assert draft.id != published.id
        assert draft.layout == {"elements": ["v1"]}

        await repository.update_draft(draft, layout={"elements": ["v2"]})

        assert published.layout == {"elements": ["v1"]}

    async def test_get_or_create_draft_reuses_an_existing_draft(
        self, repository, sheet
    ):
        first = await repository.get_or_create_draft(sheet)

        assert (await repository.get_or_create_draft(sheet)).id == first.id

    async def test_published_versions_are_immutable(self, repository, sheet):
        published = await repository.publish(await repository.get_draft(sheet.id))

        with pytest.raises(ValueError):
            await repository.update_draft(published, layout={})
        with pytest.raises(ValueError):
            await repository.publish(published)

    async def test_get_version_still_works_after_the_sheet_is_deleted(
        self, repository, sheet
    ):
        published = await repository.publish(await repository.get_draft(sheet.id))

        await repository.delete(sheet)

        assert await repository.get(sheet.id) is None
        assert (await repository.get_version(published.id)).layout == {
            "elements": ["v1"]
        }
