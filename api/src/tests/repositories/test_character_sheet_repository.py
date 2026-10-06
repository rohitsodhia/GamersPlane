import re

import pytest
from sqlalchemy import select

from app.character_sheets.defaults import default_sheet_layout
from app.character_sheets.layout_validation import SCHEMA_VERSION
from app.models import CharacterSheet
from app.repositories import CharacterSheetRepository
from tests.factories import ActivatedUserFactory, SystemFactory


def _strip_ids(node):
    """Recursively drop minted `id` keys, for comparing layouts by shape."""
    if isinstance(node, dict):
        return {k: _strip_ids(v) for k, v in node.items() if k != "id"}
    if isinstance(node, list):
        return [_strip_ids(item) for item in node]
    return node


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

    async def test_create_mints_ids_on_a_copy_of_the_given_layout(
        self, repository, system
    ):
        # Every caller (API, CLI) gets ids minted here -- and a caller's dict,
        # e.g. a module-level constant, isn't mutated along the way.
        layout = {"schema_version": 1, "elements": [{"type": "input", "name": "hp"}]}

        sheet = await repository.create(
            name="Fighter", system_id=system.id, layout=layout
        )

        stored = (await repository.get_draft(sheet.id)).layout
        assert re.fullmatch(r"[0-9a-f]{8}", stored["elements"][0]["id"])
        assert "id" not in layout["elements"][0]

    async def test_create_falls_back_to_the_default_layout(self, repository, system):
        sheet = await repository.create(name="Fighter", system_id=system.id)

        # Field ids are minted on top of the canned default -- same shape once
        # they're stripped back out.
        layout = (await repository.get_draft(sheet.id)).layout
        assert _strip_ids(layout) == default_sheet_layout()


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
        first = await repository.publish(await repository.get_draft(sheet.id))
        second = await repository.publish(
            await repository.save_draft(sheet, layout={"elements": ["v2"]})
        )

        assert (first.number, second.number) == (1, 2)
        assert first.published_at is not None
        assert not first.is_draft

    async def test_get_latest_published_ignores_the_draft(self, repository, sheet):
        assert await repository.get_latest_published(sheet.id) is None

        published = await repository.publish(await repository.get_draft(sheet.id))
        assert (
            await repository.save_draft(sheet, layout={"elements": ["v2"]})
        ).is_draft

        assert (await repository.get_latest_published(sheet.id)).id == published.id

    async def test_get_published_is_scoped_to_the_sheet(self, repository, sheet):
        other = await repository.create(name="Wizard", system_id=sheet.system_id)
        await repository.publish(await repository.get_draft(other.id))
        published = await repository.publish(await repository.get_draft(sheet.id))

        assert (await repository.get_published(sheet.id, 1)).id == published.id
        assert await repository.get_published(sheet.id, 2) is None

    async def test_save_draft_updates_an_existing_draft_in_place(
        self, repository, sheet
    ):
        initial = await repository.get_draft(sheet.id)

        saved = await repository.save_draft(sheet, layout={"elements": ["v2"]})

        assert saved.id == initial.id
        assert saved.layout == {"elements": ["v2"]}

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
