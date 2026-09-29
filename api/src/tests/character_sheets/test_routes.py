import re

import pytest
from sqlalchemy import select
from sqlalchemy.orm import undefer

from app.character_sheets.defaults import default_sheet_layout
from app.configs import configs
from app.models import CharacterSheet, CharacterSheetFavorite, CharacterSheetVersion
from app.repositories import CharacterSheetRepository
from tests.factories import ActivatedUserFactory, SystemFactory, prose_doc


def _strip_ids(node):
    """Recursively drop minted `id` keys, for comparing layouts by shape."""
    if isinstance(node, dict):
        return {k: _strip_ids(v) for k, v in node.items() if k != "id"}
    if isinstance(node, list):
        return [_strip_ids(item) for item in node]
    return node


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

        sheet = await db_session.get(CharacterSheet, sheet_id)
        assert sheet is not None
        assert sheet.creator_id == user.id
        assert sheet.name == "Fighter"
        assert sheet.system_id == system.id
        assert sheet.status == CharacterSheet.Status.PRIVATE

        # A new sheet starts as an unpublished draft holding the default layout.
        versions = list(
            await db_session.scalars(
                select(CharacterSheetVersion)
                .where(CharacterSheetVersion.character_sheet_id == sheet_id)
                .options(undefer(CharacterSheetVersion.layout))
            )
        )
        assert len(versions) == 1
        assert versions[0].is_draft
        assert versions[0].number is None
        # Field ids are minted on top of the canned default -- same shape once
        # they're stripped back out.
        assert _strip_ids(versions[0].layout) == default_sheet_layout()
        name_input = versions[0].layout["elements"][0]["content"][0]["content"][1]
        assert re.fullmatch(r"[0-9a-f]{8}", name_input["id"])


async def _make_sheet(db_session, creator, system, name="Sheet", *, status=None):
    sheet = await CharacterSheetRepository(db_session, principal=creator).create(
        name=name, system_id=system.id
    )
    if status is not None:
        sheet.status = status
        await db_session.flush()
    return sheet


async def _favorite(db_session, user, sheet):
    db_session.add(CharacterSheetFavorite(user_id=user.id, character_sheet_id=sheet.id))
    await db_session.flush()


class TestGetMyCharSheets:
    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e", name="D&D 5e")

    @pytest.fixture
    async def user(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def other(self, create):
        return await create(ActivatedUserFactory)

    async def test_requires_auth(self, client):
        response = await client.get("/character_sheets/my")

        assert response.status_code == 403

    async def test_returns_only_the_callers_own_created_sheets(
        self, client, system, user, other, db_session, auth_as
    ):
        mine = await _make_sheet(db_session, user, system, "Mine")
        await _make_sheet(db_session, other, system, "Theirs")
        auth_as(user)

        response = await client.get("/character_sheets/my")

        assert response.status_code == 200
        assert response.json() == {
            "char_sheets": [
                {
                    "id": mine.id,
                    "name": "Mine",
                    "creator": {"id": user.id, "username": user.username},
                    "system": {"id": "dnd5e", "name": "D&D 5e"},
                    "description": None,
                    "favorited": False,
                }
            ],
            "total": 1,
            "page": 1,
        }

    async def test_includes_favorited_public_sheets_from_other_creators(
        self, client, system, user, other, db_session, auth_as
    ):
        fav = await _make_sheet(
            db_session, other, system, "Borrowed", status=CharacterSheet.Status.PUBLIC
        )
        await _favorite(db_session, user, fav)
        auth_as(user)

        response = await client.get("/character_sheets/my")

        body = response.json()
        assert [s["id"] for s in body["char_sheets"]] == [fav.id]
        assert body["char_sheets"][0]["favorited"] is True

    async def test_includes_favorited_official_sheets(
        self, client, system, user, other, db_session, auth_as
    ):
        fav = await _make_sheet(
            db_session, other, system, "Blessed", status=CharacterSheet.Status.OFFICIAL
        )
        await _favorite(db_session, user, fav)
        auth_as(user)

        response = await client.get("/character_sheets/my")

        assert [s["id"] for s in response.json()["char_sheets"]] == [fav.id]

    @pytest.mark.parametrize(
        "status", [CharacterSheet.Status.PRIVATE, CharacterSheet.Status.RETIRED]
    )
    async def test_excludes_favorites_that_are_no_longer_public(
        self, client, system, user, other, db_session, auth_as, status
    ):
        fav = await _make_sheet(db_session, other, system, "Pulled", status=status)
        await _favorite(db_session, user, fav)
        auth_as(user)

        response = await client.get("/character_sheets/my")

        assert response.json()["char_sheets"] == []

    async def test_a_favorited_own_sheet_appears_once(
        self, client, system, user, db_session, auth_as
    ):
        sheet = await _make_sheet(db_session, user, system, "Solo")
        await _favorite(db_session, user, sheet)
        auth_as(user)

        response = await client.get("/character_sheets/my")

        body = response.json()
        assert [s["id"] for s in body["char_sheets"]] == [sheet.id]
        assert body["char_sheets"][0]["favorited"] is True
        assert body["total"] == 1

    async def test_orders_by_system_then_name(
        self, client, system, user, create, db_session, auth_as
    ):
        pf2e = await create(SystemFactory, id="pf2e", name="Pathfinder 2e")
        await _make_sheet(db_session, user, pf2e, "Alpha")
        await _make_sheet(db_session, user, system, "Zeta")
        await _make_sheet(db_session, user, system, "Beta")
        auth_as(user)

        response = await client.get("/character_sheets/my")

        assert [s["name"] for s in response.json()["char_sheets"]] == [
            "Beta",
            "Zeta",
            "Alpha",
        ]

    async def test_filters_by_search(self, client, system, user, db_session, auth_as):
        await _make_sheet(db_session, user, system, "Fighter")
        await _make_sheet(db_session, user, system, "Wizard")
        auth_as(user)

        response = await client.get("/character_sheets/my", params={"search": "FIGH"})

        body = response.json()
        assert [s["name"] for s in body["char_sheets"]] == ["Fighter"]
        assert body["total"] == 1

    async def test_filters_by_system(
        self, client, system, user, create, db_session, auth_as
    ):
        pf2e = await create(SystemFactory, id="pf2e", name="Pathfinder 2e")
        await _make_sheet(db_session, user, system, "Fighter")
        await _make_sheet(db_session, user, pf2e, "Champion")
        auth_as(user)

        response = await client.get(
            "/character_sheets/my", params={"system_id": "pf2e"}
        )

        assert [s["name"] for s in response.json()["char_sheets"]] == ["Champion"]

    async def test_paginates_results(self, client, system, user, db_session, auth_as):
        per_page = configs.PAGINATE_PER_PAGE
        for i in range(per_page + 1):
            await _make_sheet(db_session, user, system, f"Sheet {i:03}")
        auth_as(user)

        first = (await client.get("/character_sheets/my")).json()
        second = (await client.get("/character_sheets/my", params={"page": 2})).json()

        assert first["total"] == per_page + 1
        assert first["page"] == 1
        assert len(first["char_sheets"]) == per_page
        assert second["page"] == 2
        assert len(second["char_sheets"]) == 1

    async def test_page_below_one_is_clamped(
        self, client, system, user, db_session, auth_as
    ):
        await _make_sheet(db_session, user, system, "Only")
        auth_as(user)

        response = await client.get("/character_sheets/my", params={"page": 0})

        body = response.json()
        assert body["page"] == 1
        assert len(body["char_sheets"]) == 1


class TestGetCharSheetLibrary:
    @pytest.fixture
    async def system(self, create):
        return await create(SystemFactory, id="dnd5e", name="D&D 5e")

    @pytest.fixture
    async def viewer(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def creator(self, create):
        return await create(ActivatedUserFactory)

    async def test_requires_auth(self, client):
        response = await client.get("/character_sheets/library")

        assert response.status_code == 403

    async def test_returns_the_expected_shape_with_status(
        self, client, system, viewer, creator, db_session, auth_as
    ):
        sheet = await _make_sheet(
            db_session,
            creator,
            system,
            "Fighter",
            status=CharacterSheet.Status.OFFICIAL,
        )
        auth_as(viewer)

        response = await client.get("/character_sheets/library")

        assert response.status_code == 200
        assert response.json() == {
            "char_sheets": [
                {
                    "id": sheet.id,
                    "name": "Fighter",
                    "system": {"id": "dnd5e", "name": "D&D 5e"},
                    "creator": {"id": creator.id, "username": creator.username},
                    "description": None,
                    "status": "official",
                    "favorited": False,
                }
            ],
            "total": 1,
            "page": 1,
        }

    async def test_includes_public_and_official_but_not_private_or_retired(
        self, client, system, viewer, creator, db_session, auth_as
    ):
        Status = CharacterSheet.Status
        public = await _make_sheet(
            db_session, creator, system, "A", status=Status.PUBLIC
        )
        official = await _make_sheet(
            db_session, creator, system, "B", status=Status.OFFICIAL
        )
        await _make_sheet(db_session, creator, system, "C", status=Status.PRIVATE)
        await _make_sheet(db_session, creator, system, "D", status=Status.RETIRED)
        auth_as(viewer)

        response = await client.get("/character_sheets/library")

        body = response.json()
        assert {s["id"]: s["status"] for s in body["char_sheets"]} == {
            public.id: "public",
            official.id: "official",
        }
        assert body["total"] == 2

    async def test_excludes_the_viewers_own_sheets(
        self, client, system, viewer, db_session, auth_as
    ):
        await _make_sheet(
            db_session, viewer, system, "Mine", status=CharacterSheet.Status.PUBLIC
        )
        auth_as(viewer)

        response = await client.get("/character_sheets/library")

        assert response.json()["char_sheets"] == []

    async def test_marks_only_sheets_favorited_by_the_viewer(
        self, client, system, viewer, creator, create, db_session, auth_as
    ):
        Status = CharacterSheet.Status
        other = await create(ActivatedUserFactory)
        mine = await _make_sheet(db_session, creator, system, "A", status=Status.PUBLIC)
        theirs = await _make_sheet(
            db_session, creator, system, "B", status=Status.PUBLIC
        )
        await _favorite(db_session, viewer, mine)
        await _favorite(db_session, other, theirs)
        auth_as(viewer)

        response = await client.get("/character_sheets/library")

        body = response.json()
        assert {s["id"]: s["favorited"] for s in body["char_sheets"]} == {
            mine.id: True,
            theirs.id: False,
        }
        assert body["total"] == 2

    async def test_filters_by_search(
        self, client, system, viewer, creator, db_session, auth_as
    ):
        Status = CharacterSheet.Status
        await _make_sheet(db_session, creator, system, "Fighter", status=Status.PUBLIC)
        await _make_sheet(db_session, creator, system, "Wizard", status=Status.PUBLIC)
        auth_as(viewer)

        response = await client.get(
            "/character_sheets/library", params={"search": "wiz"}
        )

        assert [s["name"] for s in response.json()["char_sheets"]] == ["Wizard"]

    async def test_filters_by_multiple_systems(
        self, client, system, viewer, creator, create, db_session, auth_as
    ):
        Status = CharacterSheet.Status
        pf2e = await create(SystemFactory, id="pf2e", name="Pathfinder 2e")
        coc = await create(SystemFactory, id="coc", name="Call of Cthulhu")
        await _make_sheet(db_session, creator, system, "Fighter", status=Status.PUBLIC)
        await _make_sheet(db_session, creator, pf2e, "Champion", status=Status.PUBLIC)
        await _make_sheet(
            db_session, creator, coc, "Investigator", status=Status.PUBLIC
        )
        auth_as(viewer)

        response = await client.get(
            "/character_sheets/library", params={"systems": ["dnd5e", "pf2e"]}
        )

        body = response.json()
        assert sorted(s["name"] for s in body["char_sheets"]) == [
            "Champion",
            "Fighter",
        ]
        assert body["total"] == 2

    async def test_paginates_results(
        self, client, system, viewer, creator, db_session, auth_as
    ):
        per_page = configs.PAGINATE_PER_PAGE
        for i in range(per_page + 1):
            await _make_sheet(
                db_session,
                creator,
                system,
                f"Sheet {i:03}",
                status=CharacterSheet.Status.PUBLIC,
            )
        auth_as(viewer)

        first = (await client.get("/character_sheets/library")).json()
        second = (
            await client.get("/character_sheets/library", params={"page": 2})
        ).json()

        assert first["total"] == per_page + 1
        assert len(first["char_sheets"]) == per_page
        assert second["page"] == 2
        assert len(second["char_sheets"]) == 1

    async def test_page_below_one_is_clamped(
        self, client, system, viewer, creator, db_session, auth_as
    ):
        await _make_sheet(
            db_session, creator, system, "Only", status=CharacterSheet.Status.PUBLIC
        )
        auth_as(viewer)

        response = await client.get("/character_sheets/library", params={"page": 0})

        body = response.json()
        assert body["page"] == 1
        assert len(body["char_sheets"]) == 1


class TestDeleteCharSheet:
    @pytest.fixture
    async def creator(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def sheet(self, creator, create, db_session, wrap_in_savepoint):
        system = await create(SystemFactory, id="dnd5e")
        return await _make_sheet(db_session, creator, system, "Fighter")

    async def test_requires_auth(self, client, sheet):
        response = await client.delete(f"/character_sheets/{sheet.id}")

        assert response.status_code == 403

    async def test_returns_404_when_missing(self, authed_client):
        client, _user = authed_client

        response = await client.delete("/character_sheets/999999")

        assert response.status_code == 404

    async def test_forbids_non_creator(
        self, client, sheet, create, db_session, auth_as
    ):
        other = await create(ActivatedUserFactory)
        auth_as(other)

        response = await client.delete(f"/character_sheets/{sheet.id}")

        assert response.status_code == 403
        await db_session.refresh(sheet, ["deleted"])
        assert sheet.deleted is None

    async def test_soft_deletes_and_clears_favorites(
        self, client, sheet, creator, create, db_session, auth_as
    ):
        fan = await create(ActivatedUserFactory)
        await _favorite(db_session, fan, sheet)
        await _favorite(db_session, creator, sheet)
        auth_as(creator)

        response = await client.delete(f"/character_sheets/{sheet.id}")

        assert response.status_code == 204
        row = await db_session.scalar(
            select(CharacterSheet)
            .where(CharacterSheet.id == sheet.id)
            .execution_options(skip_filter=True, populate_existing=True)
        )
        assert row is not None
        assert row.deleted is not None
        favorites = await db_session.scalars(
            select(CharacterSheetFavorite).where(
                CharacterSheetFavorite.character_sheet_id == sheet.id
            )
        )
        assert favorites.all() == []


class TestToggleCharSheetFavorite:
    @pytest.fixture
    async def creator(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def viewer(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def sheet(self, creator, create, db_session, wrap_in_savepoint):
        system = await create(SystemFactory, id="dnd5e")
        return await _make_sheet(db_session, creator, system, "Fighter")

    @staticmethod
    async def _favorite_user_ids(db_session, sheet):
        rows = await db_session.scalars(
            select(CharacterSheetFavorite.user_id).where(
                CharacterSheetFavorite.character_sheet_id == sheet.id
            )
        )
        return set(rows)

    async def test_requires_auth(self, client, sheet):
        response = await client.patch(f"/character_sheets/{sheet.id}/toggle_favorite")

        assert response.status_code == 403

    async def test_returns_404_when_missing(self, authed_client):
        client, _user = authed_client

        response = await client.patch("/character_sheets/999999/toggle_favorite")

        assert response.status_code == 404

    async def test_forbids_favoriting_another_users_private_sheet(
        self, client, sheet, viewer, db_session, auth_as
    ):
        auth_as(viewer)

        response = await client.patch(f"/character_sheets/{sheet.id}/toggle_favorite")

        assert response.status_code == 403
        assert await self._favorite_user_ids(db_session, sheet) == set()

    async def test_creator_can_favorite_their_own_private_sheet(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)

        response = await client.patch(f"/character_sheets/{sheet.id}/toggle_favorite")

        assert response.status_code == 200
        assert response.json() == {"favorited": True}
        assert await self._favorite_user_ids(db_session, sheet) == {creator.id}

    async def test_toggles_on_and_off_for_a_public_sheet(
        self, client, sheet, viewer, db_session, auth_as
    ):
        sheet.status = CharacterSheet.Status.PUBLIC
        await db_session.flush()
        auth_as(viewer)

        on = await client.patch(f"/character_sheets/{sheet.id}/toggle_favorite")
        assert on.json() == {"favorited": True}
        assert await self._favorite_user_ids(db_session, sheet) == {viewer.id}

        off = await client.patch(f"/character_sheets/{sheet.id}/toggle_favorite")
        assert off.json() == {"favorited": False}
        assert await self._favorite_user_ids(db_session, sheet) == set()

    async def test_official_sheets_can_be_favorited(
        self, client, sheet, viewer, auth_as, db_session
    ):
        sheet.status = CharacterSheet.Status.OFFICIAL
        await db_session.flush()
        auth_as(viewer)

        response = await client.patch(f"/character_sheets/{sheet.id}/toggle_favorite")

        assert response.json() == {"favorited": True}

    async def test_only_toggles_the_current_users_favorite(
        self, client, sheet, creator, viewer, db_session, auth_as
    ):
        sheet.status = CharacterSheet.Status.PUBLIC
        await _favorite(db_session, creator, sheet)
        auth_as(viewer)

        response = await client.patch(f"/character_sheets/{sheet.id}/toggle_favorite")

        assert response.json() == {"favorited": True}
        assert await self._favorite_user_ids(db_session, sheet) == {
            creator.id,
            viewer.id,
        }


class TestGetCharSheet:
    @pytest.fixture
    async def creator(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def sheet(self, creator, create, db_session, wrap_in_savepoint):
        system = await create(SystemFactory, id="dnd5e", name="D&D 5e")
        repository = CharacterSheetRepository(db_session, principal=creator)
        sheet = await repository.create(
            name="Fighter",
            system_id=system.id,
            layout={
                "schema_version": 1,
                "elements": [{"type": "header", "text": "Combat"}],
            },
        )
        await repository.publish(await repository.get_draft(sheet.id))
        return sheet

    @pytest.fixture
    async def version(self, sheet, creator, db_session):
        repository = CharacterSheetRepository(db_session, principal=creator)
        return await repository.get_latest_published(sheet.id)

    async def test_returns_404_when_sheet_missing(self, authed_client):
        client, _user = authed_client

        response = await client.get("/character_sheets/999999")

        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "not_found"

    @pytest.fixture
    async def unpublished_sheet(self, creator, create, db_session):
        system = await create(SystemFactory, id="pf2e")
        return await CharacterSheetRepository(db_session, principal=creator).create(
            name="Wip", system_id=system.id
        )

    @pytest.fixture
    async def sheet_with_draft(self, sheet, creator, db_session):
        repository = CharacterSheetRepository(db_session, principal=creator)
        await repository.save_draft(sheet, layout={"schema_version": 1, "elements": []})
        return sheet

    async def test_returns_the_draft_of_an_unpublished_sheet_to_the_creator(
        self, client, unpublished_sheet, creator, auth_as
    ):
        auth_as(creator)

        response = await client.get(f"/character_sheets/{unpublished_sheet.id}")

        assert response.status_code == 200
        assert response.json()["is_draft"] is True
        assert response.json()["version_number"] is None
        assert response.json()["latest_version_number"] is None

    async def test_returns_404_for_an_unpublished_sheet_to_non_creators(
        self, client, unpublished_sheet, create, db_session, auth_as
    ):
        unpublished_sheet.status = CharacterSheet.Status.PUBLIC
        await db_session.flush()
        auth_as(await create(ActivatedUserFactory))

        response = await client.get(f"/character_sheets/{unpublished_sheet.id}")

        assert response.status_code == 404

    async def test_returns_the_draft_over_the_published_version_to_the_creator(
        self, client, sheet_with_draft, creator, auth_as
    ):
        auth_as(creator)

        response = await client.get(f"/character_sheets/{sheet_with_draft.id}")

        assert response.status_code == 200
        assert response.json()["is_draft"] is True
        assert response.json()["layout"]["elements"] == []
        # So the draft can be shown as the upcoming v2.
        assert response.json()["latest_version_number"] == 1

    @pytest.mark.parametrize(
        "status", [CharacterSheet.Status.PRIVATE, CharacterSheet.Status.RETIRED]
    )
    async def test_forbids_non_creators_on_a_sheet_that_is_not_public(
        self, client, sheet, create, db_session, auth_as, status
    ):
        sheet.status = status
        await db_session.flush()
        auth_as(await create(ActivatedUserFactory))

        response = await client.get(f"/character_sheets/{sheet.id}")

        assert response.status_code == 403

    async def test_returns_the_latest_published_version_to_non_creators(
        self, client, sheet_with_draft, create, db_session, auth_as
    ):
        sheet_with_draft.status = CharacterSheet.Status.PUBLIC
        await db_session.flush()
        auth_as(await create(ActivatedUserFactory))

        response = await client.get(f"/character_sheets/{sheet_with_draft.id}")

        assert response.status_code == 200
        assert response.json()["is_draft"] is False
        assert response.json()["layout"]["elements"] == [
            {"type": "header", "text": "Combat"}
        ]

    async def test_returns_the_serialized_sheet(
        self, client, sheet, version, creator, auth_as
    ):
        # `sheet` was published with no draft since, so this also covers the
        # creator falling back to the latest published version.
        auth_as(creator)

        response = await client.get(f"/character_sheets/{sheet.id}")

        assert response.status_code == 200
        assert response.json() == {
            "id": sheet.id,
            "creator": {"id": creator.id, "username": creator.username},
            "forked_from_id": None,
            "name": "Fighter",
            "system": {"id": "dnd5e", "name": "D&D 5e"},
            "description": None,
            "version_id": version.id,
            "version_number": 1,
            "latest_version_number": 1,
            "is_draft": False,
            "changelog": None,
            "layout": {
                "schema_version": 1,
                "elements": [{"type": "header", "text": "Combat"}],
            },
            "status": "private",
            "removed_fields": [],
        }

    async def test_version_returns_that_published_version(
        self, client, sheet_with_draft, creator, create, db_session, auth_as
    ):
        repository = CharacterSheetRepository(db_session, principal=creator)
        await repository.publish(await repository.get_draft(sheet_with_draft.id))
        sheet_with_draft.status = CharacterSheet.Status.PUBLIC
        await db_session.flush()
        auth_as(await create(ActivatedUserFactory))

        response = await client.get(
            f"/character_sheets/{sheet_with_draft.id}?version=1"
        )

        assert response.status_code == 200
        assert response.json()["version_number"] == 1
        assert response.json()["layout"]["elements"] == [
            {"type": "header", "text": "Combat"}
        ]

    async def test_version_returns_404_when_the_number_does_not_exist(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)

        response = await client.get(f"/character_sheets/{sheet.id}?version=2")

        assert response.status_code == 404
        assert response.json()["errors"][0]["detail"] == (
            "Character sheet version not found"
        )

    async def test_version_draft_returns_the_draft_to_the_creator(
        self, client, sheet_with_draft, creator, auth_as
    ):
        auth_as(creator)

        response = await client.get(
            f"/character_sheets/{sheet_with_draft.id}?version=draft"
        )

        assert response.status_code == 200
        assert response.json()["is_draft"] is True
        assert response.json()["layout"]["elements"] == []

    async def test_version_draft_returns_404_when_the_creator_has_no_draft(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)

        response = await client.get(f"/character_sheets/{sheet.id}?version=draft")

        assert response.status_code == 404
        assert response.json()["errors"][0]["detail"] == "Character sheet has no draft"

    async def test_version_draft_is_forbidden_to_non_creators(
        self, client, sheet, create, db_session, auth_as
    ):
        # `sheet` has no draft: a 403 rather than a 404 shows the permission
        # check runs first, so non-creators can't probe whether a draft exists.
        # Public, so the 403 comes from the draft gate, not the status gate.
        sheet.status = CharacterSheet.Status.PUBLIC
        await db_session.flush()
        auth_as(await create(ActivatedUserFactory))

        response = await client.get(f"/character_sheets/{sheet.id}?version=draft")

        assert response.status_code == 403

    async def test_version_rejects_values_other_than_a_number_or_draft(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)

        response = await client.get(f"/character_sheets/{sheet.id}?version=latest")

        assert response.status_code == 422


class TestUpdateCharSheet:
    @pytest.fixture
    async def creator(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def sheet(self, creator, create, db_session, wrap_in_savepoint):
        system = await create(SystemFactory, id="dnd5e")
        repository = CharacterSheetRepository(db_session, principal=creator)
        return await repository.create(
            name="Fighter",
            system_id=system.id,
            layout={"schema_version": 1, "elements": []},
        )

    async def test_requires_auth(self, client, sheet):
        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": {"elements": []}},
        )

        assert response.status_code == 403

    async def test_returns_404_when_sheet_missing(self, authed_client):
        client, _user = authed_client

        response = await client.patch(
            "/character_sheets/999999",
            json={"name": "Fighter", "layout": {"elements": []}},
        )

        assert response.status_code == 404

    async def test_forbids_non_creator(self, client, sheet, create, auth_as):
        other = await create(ActivatedUserFactory)
        auth_as(other)

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": {"elements": []}},
        )

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "forbidden"

    async def test_creator_saves_the_layout(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)
        new_layout = {
            "schema_version": 1,
            "elements": [{"type": "header", "text": "Combat"}],
        }

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": new_layout},
        )

        assert response.status_code == 200
        assert response.json()["layout"] == new_layout
        assert response.json()["is_draft"] is True

        draft = await CharacterSheetRepository(db_session, principal=creator).get_draft(
            sheet.id
        )
        assert draft.layout == new_layout

    async def test_creator_saves_the_name_and_description(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)
        description = prose_doc("A front-line martial build.")

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={
                "name": "Battle-Ready Fighter",
                "description": description,
                "layout": {"schema_version": 1, "elements": []},
            },
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Battle-Ready Fighter"
        assert response.json()["description"] == description

        await db_session.refresh(sheet)
        assert sheet.name == "Battle-Ready Fighter"
        assert sheet.description == description

    async def test_creator_saves_the_changelog_on_the_draft(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)
        changelog = prose_doc("Added a combat section.")

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={
                "name": "Fighter",
                "layout": {"schema_version": 1, "elements": []},
                "changelog": changelog,
            },
        )

        assert response.status_code == 200
        assert response.json()["changelog"] == changelog
        draft = await CharacterSheetRepository(db_session, principal=creator).get_draft(
            sheet.id
        )
        assert draft.changelog == changelog

    async def test_omitting_the_changelog_clears_the_drafts(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)
        layout = {"schema_version": 1, "elements": []}
        await client.patch(
            f"/character_sheets/{sheet.id}",
            json={
                "name": "Fighter",
                "layout": layout,
                "changelog": prose_doc("Added a combat section."),
            },
        )

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": layout},
        )

        assert response.status_code == 200
        assert response.json()["changelog"] is None

    async def test_omitting_description_clears_a_previously_set_one(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)
        await client.patch(
            f"/character_sheets/{sheet.id}",
            json={
                "name": "Fighter",
                "description": prose_doc("A front-line martial build."),
                "layout": {"schema_version": 1, "elements": []},
            },
        )

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": {"schema_version": 1, "elements": []}},
        )

        assert response.status_code == 200
        assert response.json()["description"] is None

    async def test_editing_a_published_sheet_leaves_the_published_layout_alone(
        self, client, sheet, creator, db_session, auth_as
    ):
        repository = CharacterSheetRepository(db_session, principal=creator)
        published = await repository.publish(await repository.get_draft(sheet.id))
        auth_as(creator)
        new_layout = {
            "schema_version": 1,
            "elements": [{"type": "header", "text": "Combat"}],
        }
        changelog = prose_doc("Added a combat header.")

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": new_layout, "changelog": changelog},
        )

        assert response.status_code == 200
        assert response.json()["version_id"] != published.id
        await db_session.refresh(published, ["layout"])
        assert published.layout == {"schema_version": 1, "elements": []}
        assert published.changelog is None
        draft = await repository.get_draft(sheet.id)
        assert draft.layout == new_layout
        assert draft.changelog == changelog

    async def test_saving_the_published_layout_unchanged_starts_no_draft(
        self, client, sheet, creator, db_session, auth_as
    ):
        repository = CharacterSheetRepository(db_session, principal=creator)
        published = await repository.publish(await repository.get_draft(sheet.id))
        auth_as(creator)

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={
                "name": "Renamed",
                "layout": {"schema_version": 1, "elements": []},
                "changelog": prose_doc("Nothing changed."),
            },
        )

        assert response.status_code == 200
        assert response.json()["version_id"] == published.id
        assert response.json()["is_draft"] is False
        # Name/description aren't versioned, so they still save.
        assert response.json()["name"] == "Renamed"
        assert await repository.get_draft(sheet.id) is None
        # The changelog belongs to a draft, and none was started.
        await db_session.refresh(published)
        assert published.changelog is None

    async def test_rejects_a_layout_off_the_sheet_profile(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={
                "name": "Renamed",
                "description": prose_doc("Should not be saved."),
                "layout": {"schema_version": 1, "elements": [{"type": "bogus"}]},
            },
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "validation_error"

        draft = await CharacterSheetRepository(db_session, principal=creator).get_draft(
            sheet.id
        )
        assert draft.layout == {"schema_version": 1, "elements": []}
        await db_session.refresh(sheet)
        assert sheet.name == "Fighter"
        assert sheet.description is None

    async def test_mints_a_blank_field_id(self, client, sheet, creator, auth_as):
        auth_as(creator)

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={
                "name": "Fighter",
                "layout": {
                    "schema_version": 1,
                    "elements": [{"type": "input", "name": "hp"}],
                },
            },
        )

        assert response.status_code == 200
        field_id = response.json()["layout"]["elements"][0]["id"]
        assert re.fullmatch(r"[0-9a-f]{8}", field_id)

    async def test_leaves_a_hand_authored_field_id_alone(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={
                "name": "Fighter",
                "layout": {
                    "schema_version": 1,
                    "elements": [{"type": "input", "name": "hp", "id": "custom-id"}],
                },
            },
        )

        assert response.status_code == 200
        assert response.json()["layout"]["elements"][0]["id"] == "custom-id"


VALID_LAYOUT = {
    "schema_version": 1,
    "elements": [
        {
            "type": "section",
            "content": [
                {"type": "input", "name": "name"},
                {"type": "textarea", "name": "notes"},
            ],
        }
    ],
}


def _add_input_field(layout):
    """A copy of `layout` (ids and all) with one new `input` appended -- a
    genuine change."""
    return {
        **layout,
        "elements": [*layout["elements"], {"type": "input", "name": "hp"}],
    }


class TestPublishCharSheet:
    @pytest.fixture
    async def creator(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def sheet(self, creator, create, db_session, wrap_in_savepoint):
        system = await create(SystemFactory, id="dnd5e")
        repository = CharacterSheetRepository(db_session, principal=creator)
        return await repository.create(
            name="Fighter", system_id=system.id, layout=VALID_LAYOUT
        )

    async def test_requires_auth(self, client, sheet):
        response = await client.post(f"/character_sheets/{sheet.id}/publish", json={})

        assert response.status_code == 403

    async def test_returns_404_when_sheet_missing(self, authed_client):
        client, _user = authed_client

        response = await client.post("/character_sheets/999999/publish", json={})

        assert response.status_code == 404

    async def test_forbids_non_creator(self, client, sheet, create, auth_as):
        auth_as(await create(ActivatedUserFactory))

        response = await client.post(f"/character_sheets/{sheet.id}/publish", json={})

        assert response.status_code == 403

    async def test_publishes_the_draft_as_version_one(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)
        changelog = prose_doc("First release")
        await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": VALID_LAYOUT, "changelog": changelog},
        )

        response = await client.post(f"/character_sheets/{sheet.id}/publish")

        assert response.status_code == 200
        assert response.json()["version_number"] == 1
        assert response.json()["latest_version_number"] == 1
        assert response.json()["is_draft"] is False
        assert response.json()["changelog"] == changelog
        repository = CharacterSheetRepository(db_session, principal=creator)
        version = await repository.get_latest_published(sheet.id)
        assert version.changelog == changelog
        assert await repository.get_draft(sheet.id) is None

    async def test_second_publish_increments_the_number(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)
        first = await client.post(f"/character_sheets/{sheet.id}/publish", json={})
        await client.patch(
            f"/character_sheets/{sheet.id}",
            json={
                "name": "Fighter",
                "layout": _add_input_field(first.json()["layout"]),
            },
        )

        response = await client.post(f"/character_sheets/{sheet.id}/publish", json={})

        assert response.status_code == 200
        assert response.json()["version_number"] == 2

    async def test_conflicts_when_there_is_no_draft(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)
        await client.post(f"/character_sheets/{sheet.id}/publish", json={})

        response = await client.post(f"/character_sheets/{sheet.id}/publish", json={})

        assert response.status_code == 409

    async def test_a_draft_matching_the_published_version_is_discarded(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)
        first = await client.post(f"/character_sheets/{sheet.id}/publish", json={})
        published_layout = first.json()["layout"]
        # Edit, then revert: the draft survives the revert, holding exactly
        # the published layout.
        await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": _add_input_field(published_layout)},
        )
        await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": published_layout},
        )
        repository = CharacterSheetRepository(db_session, principal=creator)
        assert await repository.get_draft(sheet.id) is not None

        response = await client.post(f"/character_sheets/{sheet.id}/publish", json={})

        assert response.status_code == 200
        assert response.json()["version_id"] == first.json()["version_id"]
        assert response.json()["version_number"] == 1
        assert response.json()["added_field_ids"] == []
        assert response.json()["removed_field_ids"] == []
        assert await repository.get_draft(sheet.id) is None

    async def test_rejects_a_draft_missing_the_required_fields(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)
        await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": {"schema_version": 1, "elements": []}},
        )

        response = await client.post(f"/character_sheets/{sheet.id}/publish", json={})

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "validation_error"
        repository = CharacterSheetRepository(db_session, principal=creator)
        assert await repository.get_latest_published(sheet.id) is None
        assert (await repository.get_draft(sheet.id)).is_draft

    async def test_rejects_a_draft_with_an_unresolved_ref(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)
        await client.patch(
            f"/character_sheets/{sheet.id}",
            json={
                "name": "Fighter",
                "layout": _layout_with(
                    {"type": "text", "name": "total", "formula": {"ref": "nope"}}
                ),
            },
        )

        response = await client.post(f"/character_sheets/{sheet.id}/publish", json={})

        assert response.status_code == 400
        assert "Ref 'nope'" in response.json()["errors"][0]["detail"]
        repository = CharacterSheetRepository(db_session, principal=creator)
        assert await repository.get_latest_published(sheet.id) is None


class TestDiscardCharSheetDraft:
    @pytest.fixture
    async def creator(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def sheet(self, creator, create, db_session, wrap_in_savepoint):
        """A sheet published as v1, with a draft of further edits open."""
        system = await create(SystemFactory, id="dnd5e")
        repository = CharacterSheetRepository(db_session, principal=creator)
        sheet = await repository.create(
            name="Fighter", system_id=system.id, layout=VALID_LAYOUT
        )
        published = await repository.publish(await repository.get_draft(sheet.id))
        await repository.save_draft(
            sheet,
            layout=_add_input_field(published.layout),
            changelog=prose_doc("Added a field"),
        )
        return sheet

    async def test_requires_auth(self, client, sheet):
        response = await client.delete(f"/character_sheets/{sheet.id}/draft")

        assert response.status_code == 403

    async def test_returns_404_when_sheet_missing(self, authed_client):
        client, _user = authed_client

        response = await client.delete("/character_sheets/999999/draft")

        assert response.status_code == 404

    async def test_forbids_non_creator(
        self, client, sheet, creator, create, db_session, auth_as
    ):
        auth_as(await create(ActivatedUserFactory))

        response = await client.delete(f"/character_sheets/{sheet.id}/draft")

        assert response.status_code == 403
        repository = CharacterSheetRepository(db_session, principal=creator)
        assert await repository.get_draft(sheet.id) is not None

    async def test_deletes_the_draft_and_returns_the_published_version(
        self, client, sheet, creator, db_session, auth_as
    ):
        auth_as(creator)
        repository = CharacterSheetRepository(db_session, principal=creator)
        published = await repository.get_latest_published(sheet.id)

        response = await client.delete(f"/character_sheets/{sheet.id}/draft")

        assert response.status_code == 200
        assert response.json()["version_id"] == published.id
        assert response.json()["version_number"] == 1
        assert response.json()["latest_version_number"] == 1
        assert response.json()["is_draft"] is False
        assert response.json()["layout"] == published.layout
        assert await repository.get_draft(sheet.id) is None

    async def test_returns_404_when_there_is_no_draft(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)
        await client.delete(f"/character_sheets/{sheet.id}/draft")

        response = await client.delete(f"/character_sheets/{sheet.id}/draft")

        assert response.status_code == 404
        assert response.json()["errors"][0]["detail"] == "Character sheet has no draft"

    async def test_conflicts_when_the_sheet_was_never_published(
        self, client, creator, create, db_session, auth_as
    ):
        system = await create(SystemFactory, id="pf2e")
        repository = CharacterSheetRepository(db_session, principal=creator)
        unpublished = await repository.create(name="Wizard", system_id=system.id)
        auth_as(creator)

        response = await client.delete(f"/character_sheets/{unpublished.id}/draft")

        assert response.status_code == 409
        assert await repository.get_draft(unpublished.id) is not None


def _layout_with(*elements):
    return {
        "schema_version": 1,
        "elements": [_REQUIRED_NAME, _REQUIRED_NOTES, *elements],
    }


_REQUIRED_NAME = {"type": "input", "name": "name"}
_REQUIRED_NOTES = {"type": "textarea", "name": "notes"}


class TestPublishCharSheetFieldIds:
    """Field-id minting + publish-time validation (`layout_ids.py`)."""

    @pytest.fixture
    async def creator(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def sheet(self, creator, create, db_session, wrap_in_savepoint):
        system = await create(SystemFactory, id="dnd5e")
        repository = CharacterSheetRepository(db_session, principal=creator)
        return await repository.create(name="Fighter", system_id=system.id)

    async def _save_and_publish(self, client, sheet_id, layout):
        await client.patch(
            f"/character_sheets/{sheet_id}",
            json={"name": "Fighter", "layout": layout},
        )
        return await client.post(f"/character_sheets/{sheet_id}/publish")

    async def test_first_publish_reports_every_field_as_added(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)

        response = await self._save_and_publish(
            client, sheet.id, _layout_with({"type": "input", "name": "hp"})
        )

        assert response.status_code == 200
        assert response.json()["removed_field_ids"] == []
        assert len(response.json()["added_field_ids"]) == 3

    async def test_renaming_a_field_keeps_its_id_out_of_the_diff(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)
        first = await self._save_and_publish(
            client, sheet.id, _layout_with({"type": "input", "name": "hp"})
        )
        name_el, notes_el, hp_el = first.json()["layout"]["elements"]

        second = await self._save_and_publish(
            client,
            sheet.id,
            {
                "schema_version": 1,
                "elements": [
                    name_el,
                    notes_el,
                    {"type": "input", "name": "hit_points", "id": hp_el["id"]},
                ],
            },
        )

        assert second.status_code == 200
        assert second.json()["added_field_ids"] == []
        assert second.json()["removed_field_ids"] == []

    async def test_removing_a_field_reports_its_id_as_removed(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)
        first = await self._save_and_publish(
            client, sheet.id, _layout_with({"type": "input", "name": "hp"})
        )
        name_el, notes_el, hp_el = first.json()["layout"]["elements"]

        second = await self._save_and_publish(
            client,
            sheet.id,
            {"schema_version": 1, "elements": [name_el, notes_el]},
        )

        assert second.status_code == 200
        assert second.json()["removed_field_ids"] == [hp_el["id"]]
        assert second.json()["added_field_ids"] == []

    async def test_reusing_an_id_on_a_different_field_type_is_rejected(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)
        first = await self._save_and_publish(
            client, sheet.id, _layout_with({"type": "input", "name": "hp"})
        )
        name_el, notes_el, hp_el = first.json()["layout"]["elements"]

        response = await self._save_and_publish(
            client,
            sheet.id,
            {
                "schema_version": 1,
                "elements": [
                    name_el,
                    notes_el,
                    {"type": "textarea", "name": "hp", "id": hp_el["id"]},
                ],
            },
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "validation_error"
        assert (
            "changed from a 'input' to a 'textarea'"
            in response.json()["errors"][0]["detail"]
        )

    async def test_a_hand_authored_id_on_a_new_field_is_rejected(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)

        response = await self._save_and_publish(
            client,
            sheet.id,
            _layout_with({"type": "input", "name": "hp", "id": "not-server-minted"}),
        )

        assert response.status_code == 400
        assert "wasn't assigned by the server" in response.json()["errors"][0]["detail"]

    async def test_a_duplicate_id_is_rejected(
        self, client, sheet, creator, db_session, auth_as
    ):
        # Writes the draft row directly, bypassing the repository's `mint_ids`,
        # which would otherwise self-heal the duplicate before publish ever
        # sees it -- this exercises publish's own defensive check.
        repository = CharacterSheetRepository(db_session, principal=creator)
        # A freshly created sheet's initial draft.
        draft = await repository.get_draft(sheet.id)
        draft.layout = _layout_with(
            {"type": "input", "name": "hp", "id": "aaaaaaaa"},
            {"type": "input", "name": "mp", "id": "aaaaaaaa"},
        )
        await db_session.flush()
        auth_as(creator)

        response = await client.post(f"/character_sheets/{sheet.id}/publish", json={})

        assert response.status_code == 400
        assert "used more than once" in response.json()["errors"][0]["detail"]


class TestDraftRemovedFields:
    """`removed_fields` on a draft: what publishing it would drop."""

    @pytest.fixture
    async def creator(self, create):
        return await create(ActivatedUserFactory)

    @pytest.fixture
    async def sheet(self, creator, create, db_session, wrap_in_savepoint):
        """A sheet published as v1 with an `hp` field."""
        system = await create(SystemFactory, id="dnd5e")
        repository = CharacterSheetRepository(db_session, principal=creator)
        sheet = await repository.create(
            name="Fighter",
            system_id=system.id,
            layout=_layout_with({"type": "input", "name": "hp"}),
        )
        await repository.publish(await repository.get_draft(sheet.id))
        return sheet

    async def _published_elements(self, db_session, creator, sheet):
        repository = CharacterSheetRepository(db_session, principal=creator)
        return (await repository.get_latest_published(sheet.id)).layout["elements"]

    async def test_saving_a_draft_reports_the_dropped_fields(
        self, client, sheet, creator, db_session, auth_as
    ):
        name_el, notes_el, hp_el = await self._published_elements(
            db_session, creator, sheet
        )
        auth_as(creator)

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={
                "name": "Fighter",
                "layout": {"schema_version": 1, "elements": [name_el, notes_el]},
            },
        )

        assert response.status_code == 200
        assert response.json()["removed_fields"] == [{"id": hp_el["id"], "label": "hp"}]

    async def test_fetching_the_draft_reports_the_dropped_fields(
        self, client, sheet, creator, db_session, auth_as
    ):
        name_el, notes_el, hp_el = await self._published_elements(
            db_session, creator, sheet
        )
        repository = CharacterSheetRepository(db_session, principal=creator)
        await repository.save_draft(
            sheet,
            layout={"schema_version": 1, "elements": [name_el, notes_el]},
            changelog=None,
        )
        auth_as(creator)

        response = await client.get(f"/character_sheets/{sheet.id}")

        assert response.json()["is_draft"] is True
        assert response.json()["removed_fields"] == [{"id": hp_el["id"], "label": "hp"}]

    async def test_a_published_version_reports_nothing(
        self, client, sheet, creator, db_session, auth_as
    ):
        name_el, notes_el, _hp_el = await self._published_elements(
            db_session, creator, sheet
        )
        repository = CharacterSheetRepository(db_session, principal=creator)
        await repository.save_draft(
            sheet,
            layout={"schema_version": 1, "elements": [name_el, notes_el]},
            changelog=None,
        )
        auth_as(creator)

        response = await client.get(f"/character_sheets/{sheet.id}?version=1")

        assert response.json()["is_draft"] is False
        assert response.json()["removed_fields"] == []

    async def test_a_never_published_draft_reports_nothing(
        self, client, creator, create, db_session, auth_as
    ):
        system = await create(SystemFactory, id="pf2e")
        repository = CharacterSheetRepository(db_session, principal=creator)
        unpublished = await repository.create(name="Wizard", system_id=system.id)
        auth_as(creator)

        response = await client.get(f"/character_sheets/{unpublished.id}")

        assert response.json()["is_draft"] is True
        assert response.json()["removed_fields"] == []
