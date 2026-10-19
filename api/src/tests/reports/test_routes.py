from dataclasses import dataclass
from typing import Awaitable, Callable

import pytest
from sqlalchemy import func, select

from app.configs import configs
from app.models import (
    CharacterAvatar,
    Game,
    NPCImage,
    Post,
    QuickNPC,
    Report,
    RolePermission,
    UserMeta,
)
from app.reports.routes import REPORTS_PER_HOUR
from app.repositories import UserRepository
from tests.conftest import SITE_ROOT_FORUM_ID
from tests.factories import (
    ActivatedUserFactory,
    ForumFactory,
    PostFactory,
    RoleFactory,
    ThreadFactory,
)
from tests.game_forum import (
    add_avatar,
    make_character,
    make_game_forum,
    make_game_image,
    make_npc,
)

Verbs = RolePermission.ValidPermissions
Statuses = Report.Statuses
BACKGROUND_FILE = "0123456789abcdef0123456789abcdef.png"
IMAGE_KINDS = ["user_avatar", "character_avatar", "game_background", "npc_image"]


@pytest.fixture(autouse=True)
async def _open_site_root(wrap_in_savepoint, open_forums):
    """Ordinary member access under the site root, so posts and threads there are
    readable."""
    await open_forums(SITE_ROOT_FORUM_ID)


@pytest.fixture(autouse=True)
def _tmp_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(configs, "AVATARS_DIR", str(tmp_path / "avatars"))
    monkeypatch.setattr(configs, "BACKGROUNDS_DIR", str(tmp_path / "backgrounds"))
    monkeypatch.setattr(configs, "QUARANTINE_DIR", str(tmp_path / "quarantine"))


@pytest.fixture
async def staff(create, db_session):
    user = await create(ActivatedUserFactory)
    role = RoleFactory.build(owner=user)
    db_session.add(role)
    role.grant(Verbs.MANAGE_REPORTS)
    user.roles.append(role)
    await db_session.flush()
    return user


@pytest.fixture
async def reporter(create):
    return await create(ActivatedUserFactory)


def report_body(target_type, target_id, reason="spam", **overrides):
    return {
        "target_type": target_type,
        "target_id": target_id,
        "reason": reason,
        **overrides,
    }


def write_file(path, content=b"image-bytes"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


@dataclass
class ImageTarget:
    kind: str
    id: int
    live: object
    # Whether the app no longer has the image.
    is_reset: Callable[[], Awaitable[bool]]


@pytest.fixture
def make_image_target(create, db_session, tmp_path):
    async def _make(kind: str, with_file: bool = True) -> ImageTarget:
        avatars = tmp_path / "avatars"
        if kind == "user_avatar":
            user = await create(ActivatedUserFactory)
            await UserRepository(db_session).update_user_meta(
                user, {UserMeta.MetaKeys.AVATAR_EXT: "png"}
            )
            target_id, live = user.id, avatars / "users" / f"{user.id}.png"

            async def is_reset():
                return not await db_session.scalar(
                    select(func.count())
                    .select_from(UserMeta)
                    .where(
                        UserMeta.user_id == user.id,
                        UserMeta.key == UserMeta.MetaKeys.AVATAR_EXT.value,
                    )
                )

        elif kind == "character_avatar":
            owner = await create(ActivatedUserFactory)
            character = await make_character(db_session, owner)
            target_id = await add_avatar(db_session, character)
            live = avatars / "characters" / f"{target_id}.png"

            async def is_reset():
                return not await db_session.scalar(
                    select(func.count())
                    .select_from(CharacterAvatar)
                    .where(CharacterAvatar.id == target_id)
                )

        elif kind == "game_background":
            world = await make_game_forum(create, db_session)
            world.game.advanced_options = {"background": {"image": BACKGROUND_FILE}}
            await db_session.flush()
            target_id, live = world.game.id, tmp_path / "backgrounds" / BACKGROUND_FILE

            async def is_reset():
                options = await db_session.scalar(
                    select(Game.advanced_options).where(Game.id == target_id)
                )
                return not (options or {}).get("background")

        else:
            world = await make_game_forum(create, db_session)
            image = await make_game_image(db_session, world.game, world.gm)
            target_id, live = image.id, avatars / "npcs" / f"{image.id}.png"

            async def is_reset():
                return not await db_session.scalar(
                    select(func.count())
                    .select_from(NPCImage)
                    .where(NPCImage.id == target_id)
                )

        if with_file:
            write_file(live)
        return ImageTarget(kind, target_id, live, is_reset)

    return _make


class TestCreateReport:
    async def test_files_a_report_and_returns_only_its_id_and_status(
        self, auth_as, create, reporter
    ):
        target = await create(ActivatedUserFactory)

        response = await auth_as(reporter).post(
            "/reports", json=report_body("user", target.id)
        )

        assert response.status_code == 201
        body = response.json()
        assert set(body) == {"id", "status"}
        assert body["status"] == "open"

    async def test_snapshots_a_post(self, auth_as, create, db_session, reporter):
        author = await create(ActivatedUserFactory)
        post = await create(
            PostFactory, author=author, title="Buy now", body_text="Cheap pills"
        )

        response = await auth_as(reporter).post(
            "/reports", json=report_body("post", post.id)
        )

        assert response.status_code == 201
        report = await db_session.get(Report, response.json()["id"])
        assert report.snapshot == {
            "title": "Buy now",
            "body_text": "Cheap pills",
            "author_id": author.id,
            "thread_id": post.thread_id,
        }

    async def test_snapshots_a_thread_by_its_first_post(
        self, auth_as, create, db_session, reporter
    ):
        thread = await create(ThreadFactory)
        post = await create(PostFactory, thread=thread, title="Opener", body_text="Hi")
        thread.first_post = post
        await db_session.flush()

        response = await auth_as(reporter).post(
            "/reports", json=report_body("thread", thread.id)
        )

        assert response.status_code == 201
        report = await db_session.get(Report, response.json()["id"])
        assert report.snapshot == {
            "title": "Opener",
            "body_text": "Hi",
            "author_id": post.author_id,
        }

    async def test_snapshots_a_user(self, auth_as, create, db_session, reporter):
        target = await create(ActivatedUserFactory)

        response = await auth_as(reporter).post(
            "/reports", json=report_body("user", target.id)
        )

        report = await db_session.get(Report, response.json()["id"])
        assert report.snapshot == {"username": target.username}

    async def test_snapshots_a_character(self, auth_as, create, db_session, reporter):
        owner = await create(ActivatedUserFactory)
        character = await make_character(db_session, owner, name="Aria")

        response = await auth_as(reporter).post(
            "/reports", json=report_body("character", character.id)
        )

        report = await db_session.get(Report, response.json()["id"])
        assert report.snapshot == {"name": "Aria", "user_id": owner.id}

    async def test_snapshots_a_game(self, auth_as, create, db_session, reporter):
        world = await make_game_forum(create, db_session)

        response = await auth_as(reporter).post(
            "/reports", json=report_body("game", world.game.id)
        )

        report = await db_session.get(Report, response.json()["id"])
        assert report.snapshot == {"title": "My Campaign", "gm_id": world.gm.id}

    @pytest.mark.parametrize("kind", IMAGE_KINDS)
    async def test_image_report_keeps_a_copy_of_the_live_file(
        self, kind, auth_as, db_session, reporter, make_image_target, tmp_path
    ):
        target = await make_image_target(kind)

        response = await auth_as(reporter).post(
            "/reports", json=report_body(kind, target.id)
        )

        assert response.status_code == 201
        report = await db_session.get(Report, response.json()["id"])
        assert report.snapshot["location"].endswith(f"/{target.live.name}")
        assert report.snapshot_file == f"reports/{report.id}.png"
        copy = tmp_path / "quarantine" / report.snapshot_file
        assert copy.read_bytes() == b"image-bytes"
        assert target.live.exists()

    # The shared missing-file branch, plus the game background's own check.
    @pytest.mark.parametrize("kind", ["user_avatar", "game_background"])
    async def test_image_report_is_filed_even_if_the_file_is_missing(
        self, kind, auth_as, db_session, reporter, make_image_target
    ):
        target = await make_image_target(kind, with_file=False)

        response = await auth_as(reporter).post(
            "/reports", json=report_body(kind, target.id)
        )

        assert response.status_code == 201
        report = await db_session.get(Report, response.json()["id"])
        assert report.snapshot_file is None

    async def test_user_without_an_avatar_has_no_avatar_to_report(
        self, auth_as, create, reporter
    ):
        target = await create(ActivatedUserFactory)

        response = await auth_as(reporter).post(
            "/reports", json=report_body("user_avatar", target.id)
        )

        assert response.status_code == 404

    async def test_missing_target_is_404(self, auth_as, reporter):
        response = await auth_as(reporter).post(
            "/reports", json=report_body("game", 999_999)
        )

        assert response.status_code == 404

    async def test_post_in_a_forum_the_reporter_cannot_read_is_404(
        self, auth_as, create, reporter
    ):
        forum = await create(ForumFactory, heritage=[999])
        thread = await create(ThreadFactory, forum=forum)
        post = await create(PostFactory, thread=thread)

        response = await auth_as(reporter).post(
            "/reports", json=report_body("post", post.id)
        )

        assert response.status_code == 404

    async def test_unpublished_post_is_404(self, auth_as, create, reporter):
        post = await create(PostFactory, state=Post.States.DRAFT)

        response = await auth_as(reporter).post(
            "/reports", json=report_body("post", post.id)
        )

        assert response.status_code == 404

    async def test_reporting_twice_is_a_conflict(self, auth_as, create, reporter):
        target = await create(ActivatedUserFactory)
        body = report_body("user", target.id)
        await auth_as(reporter).post("/reports", json=body)

        again = await auth_as(reporter).post("/reports", json=body)

        assert again.status_code == 409
        assert "already reported" in again.json()["errors"][0]["detail"]

    async def test_eleventh_report_in_an_hour_is_rate_limited(
        self, auth_as, create, reporter
    ):
        client = auth_as(reporter)
        for _ in range(REPORTS_PER_HOUR):
            target = await create(ActivatedUserFactory)
            response = await client.post(
                "/reports", json=report_body("user", target.id)
            )
            assert response.status_code == 201
        target = await create(ActivatedUserFactory)

        response = await client.post("/reports", json=report_body("user", target.id))

        assert response.status_code == 429

    async def test_reason_other_needs_details(self, auth_as, create, reporter):
        target = await create(ActivatedUserFactory)
        client = auth_as(reporter)

        blank = await client.post(
            "/reports", json=report_body("user", target.id, "other", details="   ")
        )
        given = await client.post(
            "/reports", json=report_body("user", target.id, "other", details="Odd")
        )

        assert blank.status_code == 422
        assert given.status_code == 201


class TestStaffEndpoints:
    async def test_need_manage_reports(self, auth_as, reporter):
        response = await auth_as(reporter).get("/reports")

        assert response.status_code == 403

    async def test_queue_lists_open_groups_with_a_total(
        self, auth_as, create, reporter, staff
    ):
        flagged, quiet = (
            await create(ActivatedUserFactory),
            await create(ActivatedUserFactory),
        )
        other = await create(ActivatedUserFactory)
        await auth_as(reporter).post("/reports", json=report_body("user", quiet.id))
        await auth_as(reporter).post(
            "/reports", json=report_body("user", flagged.id, "illegal_content")
        )
        await auth_as(other).post("/reports", json=report_body("user", flagged.id))

        response = await auth_as(staff).get("/reports")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        first, second = body["groups"]
        assert (first["target_id"], first["count"], first["reason"]) == (
            flagged.id,
            2,
            "illegal_content",
        )
        assert first["latest_snapshot"] == {"username": flagged.username}
        assert (second["target_id"], second["status"]) == (quiet.id, "open")

    async def test_target_detail_shows_who_reported_and_what(
        self, auth_as, create, reporter, staff, make_image_target
    ):
        target = await make_image_target("npc_image")
        await auth_as(reporter).post(
            "/reports",
            json=report_body("npc_image", target.id, "copyright", details="Mine"),
        )

        response = await auth_as(staff).get(f"/reports/npc_image/{target.id}")

        assert response.status_code == 200
        (report,) = response.json()["reports"]
        assert report["reporter"] == {"id": reporter.id, "username": reporter.username}
        assert (report["reason"], report["details"], report["status"]) == (
            "copyright",
            "Mine",
            "open",
        )
        assert report["has_snapshot_file"] is True
        assert report["snapshot"]["location"] == f"avatars/npcs/{target.id}.png"
        assert report["resolved_by"] is None

    async def test_target_detail_without_reports_is_404(self, auth_as, staff):
        response = await auth_as(staff).get("/reports/user/12345")

        assert response.status_code == 404

    async def test_resolve_closes_all_open_reports_on_the_target(
        self, auth_as, create, reporter, staff
    ):
        target = await create(ActivatedUserFactory)
        other = await create(ActivatedUserFactory)
        await auth_as(reporter).post("/reports", json=report_body("user", target.id))
        await auth_as(other).post("/reports", json=report_body("user", target.id))
        client = auth_as(staff)

        response = await client.post(
            f"/reports/user/{target.id}/resolve",
            json={"status": "dismissed", "note": "Fine"},
        )
        open_queue = (await client.get("/reports")).json()
        dismissed = (await client.get("/reports?status=dismissed")).json()
        detail = (await client.get(f"/reports/user/{target.id}")).json()
        again = await client.post(
            f"/reports/user/{target.id}/resolve", json={"status": "actioned"}
        )

        assert response.status_code == 200
        assert response.json() == {"resolved": 2}
        assert open_queue["groups"] == []
        assert [g["count"] for g in dismissed["groups"]] == [2]
        for report in detail["reports"]:
            assert report["status"] == "dismissed"
            assert report["resolution_note"] == "Fine"
            assert report["resolved_by"] == {
                "id": staff.id,
                "username": staff.username,
            }
        assert again.status_code == 404


class TestRemoveImage:
    @pytest.mark.parametrize("kind", IMAGE_KINDS)
    async def test_resets_the_image_and_moves_the_file_to_quarantine(
        self, kind, auth_as, db_session, reporter, staff, make_image_target, tmp_path
    ):
        target = await make_image_target(kind)
        filed = await auth_as(reporter).post(
            "/reports", json=report_body(kind, target.id)
        )

        response = await auth_as(staff).post(
            f"/reports/{kind}/{target.id}/remove-image"
        )

        assert response.status_code == 204
        assert await target.is_reset()
        assert not target.live.exists()
        (removed,) = (tmp_path / "quarantine" / "removed").iterdir()
        assert removed.name.startswith(f"{kind}_{target.id}_")
        assert removed.suffix == ".png"
        assert removed.read_bytes() == b"image-bytes"
        report = await db_session.get(Report, filed.json()["id"])
        await db_session.refresh(report)
        assert report.status is Statuses.ACTIONED
        assert report.resolution_note == "Image removed"
        assert report.resolved_by == staff.id
        # The copy taken when it was reported is untouched.
        assert (tmp_path / "quarantine" / report.snapshot_file).exists()

    @pytest.mark.parametrize("kind", ["user_avatar", "game_background"])
    async def test_tolerates_a_file_that_is_already_gone(
        self, kind, auth_as, staff, make_image_target, tmp_path
    ):
        target = await make_image_target(kind, with_file=False)

        response = await auth_as(staff).post(
            f"/reports/{kind}/{target.id}/remove-image"
        )

        assert response.status_code == 204
        assert await target.is_reset()
        assert not (tmp_path / "quarantine" / "removed").exists()

    async def test_only_images_can_be_removed(self, auth_as, create, staff):
        target = await create(ActivatedUserFactory)

        response = await auth_as(staff).post(f"/reports/user/{target.id}/remove-image")

        assert response.status_code == 400

    async def test_npcs_using_a_removed_image_lose_it_without_colliding(
        self, auth_as, create, db_session, staff
    ):
        world = await make_game_forum(create, db_session)
        image = await make_game_image(db_session, world.game, world.gm)
        imaged_dup = await make_npc(db_session, world.game, world.gm, "Bob", image)
        plain_dup = await make_npc(db_session, world.game, world.gm, "Bob")
        unique = await make_npc(db_session, world.game, world.gm, "Alice", image)

        response = await auth_as(staff).post(
            f"/reports/npc_image/{image.id}/remove-image"
        )

        assert response.status_code == 204
        rows = {
            npc.id: npc
            for npc in await db_session.scalars(
                select(QuickNPC)
                .where(QuickNPC.id.in_([imaged_dup.id, plain_dup.id, unique.id]))
                .execution_options(populate_existing=True)
            )
        }
        assert rows[unique.id].image_id is None
        assert rows[unique.id].deleted is None
        # "Bob" with no image already existed, so the imaged one is dropped.
        assert rows[imaged_dup.id].deleted is not None
        assert rows[plain_dup.id].deleted is None
