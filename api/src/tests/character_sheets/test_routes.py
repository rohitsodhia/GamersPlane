import pytest
from sqlalchemy import select
from sqlalchemy.orm import undefer

from app.character_sheets.defaults import default_sheet_layout
from app.configs import configs
from app.models import CharacterSheet, CharacterSheetFavorite, CharacterSheetVersion
from app.repositories import CharacterSheetRepository
from tests.factories import ActivatedUserFactory, SystemFactory, prose_doc


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
        assert versions[0].layout == default_sheet_layout()


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

    async def test_returns_404_when_sheet_has_no_published_version(
        self, client, creator, create, db_session, auth_as
    ):
        system = await create(SystemFactory, id="pf2e")
        wip = await CharacterSheetRepository(db_session, principal=creator).create(
            name="Wip", system_id=system.id
        )
        auth_as(creator)

        response = await client.get(f"/character_sheets/{wip.id}")

        assert response.status_code == 404

    async def test_returns_the_latest_published_layout_not_the_draft(
        self, client, sheet, creator, db_session, auth_as
    ):
        repository = CharacterSheetRepository(db_session, principal=creator)
        draft = await repository.get_or_create_draft(sheet)
        await repository.update_draft(
            draft, layout={"schema_version": 1, "elements": []}
        )
        auth_as(creator)

        response = await client.get(f"/character_sheets/{sheet.id}")

        assert response.json()["is_draft"] is False
        assert response.json()["layout"]["elements"] == [
            {"type": "header", "text": "Combat"}
        ]

    async def test_draft_returns_the_draft_to_the_creator(
        self, client, sheet, creator, db_session, auth_as
    ):
        repository = CharacterSheetRepository(db_session, principal=creator)
        draft = await repository.get_or_create_draft(sheet)
        await repository.update_draft(
            draft, layout={"schema_version": 1, "elements": []}
        )
        auth_as(creator)

        response = await client.get(f"/character_sheets/{sheet.id}?draft=true")

        assert response.status_code == 200
        assert response.json()["is_draft"] is True
        assert response.json()["version_number"] is None
        assert response.json()["layout"]["elements"] == []

    async def test_draft_starts_from_the_published_layout_when_none_exists(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)

        response = await client.get(f"/character_sheets/{sheet.id}?draft=true")

        assert response.json()["is_draft"] is True
        assert response.json()["layout"]["elements"] == [
            {"type": "header", "text": "Combat"}
        ]

    async def test_draft_is_forbidden_to_non_creators(
        self, client, sheet, create, auth_as
    ):
        auth_as(await create(ActivatedUserFactory))

        response = await client.get(f"/character_sheets/{sheet.id}?draft=true")

        assert response.status_code == 403

    async def test_returns_the_serialized_sheet(
        self, client, sheet, version, creator, auth_as
    ):
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
            "is_draft": False,
            "layout": {
                "schema_version": 1,
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

        response = await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": new_layout},
        )

        assert response.status_code == 200
        assert response.json()["version_id"] != published.id
        await db_session.refresh(published, ["layout"])
        assert published.layout == {"schema_version": 1, "elements": []}
        draft = await repository.get_draft(sheet.id)
        assert draft.layout == new_layout

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

        response = await client.post(
            f"/character_sheets/{sheet.id}/publish",
            json={"changelog": "  First release  "},
        )

        assert response.status_code == 200
        assert response.json()["version_number"] == 1
        assert response.json()["is_draft"] is False
        repository = CharacterSheetRepository(db_session, principal=creator)
        version = await repository.get_latest_published(sheet.id)
        assert version.changelog == "First release"
        assert await repository.get_draft(sheet.id) is None

    async def test_second_publish_increments_the_number(
        self, client, sheet, creator, auth_as
    ):
        auth_as(creator)
        await client.post(f"/character_sheets/{sheet.id}/publish", json={})
        await client.patch(
            f"/character_sheets/{sheet.id}",
            json={"name": "Fighter", "layout": VALID_LAYOUT},
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
