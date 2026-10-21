import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.configs import configs
from app.exceptions import NotFoundException, ValidationError
from app.forums.permissions import ForumPermissions
from app.games.functions import background_path, get_background
from app.helpers.images import quarantine_image
from app.models import Post, Report, User, UserMeta
from app.repositories import (
    CharacterRepository,
    GameRepository,
    PostRepository,
    QuickNPCRepository,
    UserRepository,
)
from app.reports import schemas
from app.threads.functions import get_readable_thread

TargetTypes = Report.TargetTypes

IMAGE_TARGET_TYPES = frozenset(
    {
        TargetTypes.USER_AVATAR,
        TargetTypes.CHARACTER_AVATAR,
        TargetTypes.GAME_BACKGROUND,
        TargetTypes.NPC_IMAGE,
    }
)


@dataclass
class ReportTarget:
    """A reported thing as it is right now."""

    # What goes into the report's snapshot.
    snapshot: dict[str, Any]
    # The model row behind it, for staff actions on it.
    entity: Any
    # Image targets only: the live file, or None if it's gone from disk.
    image_path: Path | None = None


def _not_found(target_type: TargetTypes) -> NotFoundException:
    return NotFoundException(f"{target_type.label} not found")


def _image_target(
    entity: Any, location: str, directory: str, extra: dict
) -> ReportTarget:
    """``location`` is the file's place under the uploads folder, ``directory`` the
    folder it's really in."""
    path = Path(directory) / location.rsplit("/", 1)[1]
    return ReportTarget(
        snapshot={**extra, "location": location},
        entity=entity,
        image_path=path if path.is_file() else None,
    )


async def _load_post(
    db_session: AsyncSession, principal: User, post_id: int
) -> ReportTarget:
    post = await PostRepository(db_session, principal=principal).get(post_id)
    if post is None or post.state != Post.States.PUBLISHED:
        raise _not_found(TargetTypes.POST)
    await ForumPermissions.require_read(
        db_session, principal, post.thread.forum, "Post not found"
    )
    return ReportTarget(
        snapshot={
            "title": post.title,
            "body_text": post.body_text,
            "author_id": post.author_id,
            "thread_id": post.thread_id,
        },
        entity=post,
    )


async def _load_thread(
    db_session: AsyncSession, principal: User, thread_id: int
) -> ReportTarget:
    thread, _permissions = await get_readable_thread(db_session, principal, thread_id)
    first_post = thread.first_post
    return ReportTarget(
        snapshot={
            "title": first_post.title if first_post else None,
            "body_text": first_post.body_text if first_post else None,
            "author_id": first_post.author_id if first_post else None,
        },
        entity=thread,
    )


async def load_target(
    db_session: AsyncSession,
    principal: User,
    target_type: TargetTypes,
    target_id: int,
) -> ReportTarget:
    """The target and a snapshot of it. 404 if it doesn't exist, or (for posts and
    threads) the principal can't read it."""
    if target_type is TargetTypes.POST:
        return await _load_post(db_session, principal, target_id)
    if target_type is TargetTypes.THREAD:
        return await _load_thread(db_session, principal, target_id)

    if target_type in (TargetTypes.USER, TargetTypes.USER_AVATAR):
        user = await UserRepository(db_session).get_user(target_id)
        if user is None:
            raise _not_found(target_type)
        if target_type is TargetTypes.USER:
            return ReportTarget(snapshot={"username": user.username}, entity=user)
        ext = next(
            (m.value for m in user.meta if m.key == UserMeta.MetaKeys.AVATAR_EXT.value),
            None,
        )
        if not ext:
            raise _not_found(target_type)
        return _image_target(
            user,
            f"avatars/users/{user.id}.{ext}",
            configs.AVATARS_DIR + "/users",
            {"user_id": user.id, "username": user.username},
        )

    if target_type is TargetTypes.CHARACTER:
        character = await CharacterRepository(db_session, principal=principal).get(
            target_id
        )
        if character is None:
            raise _not_found(target_type)
        return ReportTarget(
            snapshot={
                "name": character.name or character.label,
                "user_id": character.user_id,
            },
            entity=character,
        )

    if target_type is TargetTypes.CHARACTER_AVATAR:
        avatar = await CharacterRepository(db_session, principal=principal).get_avatar(
            target_id
        )
        if avatar is None:
            raise _not_found(target_type)
        return _image_target(
            avatar,
            f"avatars/characters/{avatar.id}.{avatar.ext}",
            configs.AVATARS_DIR + "/characters",
            {"character_id": avatar.character_id},
        )

    if target_type in (TargetTypes.GAME, TargetTypes.GAME_BACKGROUND):
        game = await GameRepository(db_session, principal=principal).get(target_id)
        if game is None:
            raise _not_found(target_type)
        if target_type is TargetTypes.GAME:
            return ReportTarget(
                snapshot={"title": game.title, "gm_id": game.gm_id}, entity=game
            )
        background = get_background(game.advanced_options)
        if background is None:
            raise _not_found(target_type)
        path = background_path(background.image)
        return ReportTarget(
            snapshot={
                "game_id": game.id,
                "title": game.title,
                "location": f"backgrounds/{background.image}",
            },
            entity=game,
            image_path=path if path.is_file() else None,
        )

    # NPC_IMAGE
    image = await QuickNPCRepository(db_session, principal=principal).get_image(
        target_id
    )
    if image is None:
        raise _not_found(target_type)
    return _image_target(
        image,
        f"avatars/npcs/{image.id}.{image.ext}",
        configs.AVATARS_DIR + "/npcs",
        {"game_id": image.game_id, "user_id": image.user_id},
    )


def snapshot_image(report: Report, target: ReportTarget) -> None:
    """Keep a copy of the reported image, since its owner can delete or replace the
    live file at any time. Does nothing if the file is already gone."""
    if target.image_path is None:
        return
    name = f"reports/{report.id}{target.image_path.suffix}"
    if quarantine_image(
        target.image_path, Path(configs.QUARANTINE_DIR) / name, move=False
    ):
        report.snapshot_file = name


async def remove_image(
    db_session: AsyncSession,
    staff: User,
    target_type: TargetTypes,
    target_id: int,
) -> None:
    """Take a reported image out of use and move its file to quarantine."""
    if target_type not in IMAGE_TARGET_TYPES:
        raise ValidationError("Only images can be removed")
    target = await load_target(db_session, staff, target_type, target_id)

    if target_type is TargetTypes.USER_AVATAR:
        await UserRepository(db_session).delete_user_meta(
            target.entity, UserMeta.MetaKeys.AVATAR_EXT
        )
    elif target_type is TargetTypes.CHARACTER_AVATAR:
        await CharacterRepository(db_session, principal=staff).delete_avatar_by_id(
            target_id
        )
    elif target_type is TargetTypes.GAME_BACKGROUND:
        game = target.entity
        options = dict(game.advanced_options or {})
        del options["background"]
        await GameRepository(db_session, principal=staff).update(
            game, advanced_options=options or None
        )
    else:
        await QuickNPCRepository(db_session, principal=staff).remove_image(
            target.entity
        )

    if target.image_path is not None:
        name = (
            f"removed/{target_type.value}_{target_id}_{secrets.token_hex(8)}"
            f"{target.image_path.suffix}"
        )
        quarantine_image(
            target.image_path, Path(configs.QUARANTINE_DIR) / name, move=True
        )


def build_report_data(report: Report) -> schemas.ReportData:
    resolver = report.resolver
    return schemas.ReportData(
        id=report.id,
        reporter=schemas.ReporterData(
            id=report.reporter.id, username=report.reporter.username
        ),
        reason=report.reason,
        details=report.details,
        status=report.status,
        created_at=report.created_at,
        resolved_by=(
            schemas.ReporterData(id=resolver.id, username=resolver.username)
            if resolver
            else None
        ),
        resolved_at=report.resolved_at,
        resolution_note=report.resolution_note,
        snapshot=report.snapshot,
        has_snapshot_file=report.snapshot_file is not None,
    )
