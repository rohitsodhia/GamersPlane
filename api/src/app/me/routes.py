import io
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.configs import configs
from app.database import DBSessionDependency
from app.me import schemas
from app.middleware import AuthedUser
from app.models import UserMeta
from app.repositories.user_repository import UserRepository

me = APIRouter(prefix="/me")

AVATAR_MAX_DIMENSION = 150
AVATAR_MAX_BYTES = 5 * 1024 * 1024
_AVATAR_FORMAT_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}

_PROFILE_META_KEYS: dict[str, UserMeta.MetaKeys] = {
    "pronouns": UserMeta.MetaKeys.PRONOUNS,
    "birthday": UserMeta.MetaKeys.BIRTHDAY,
    "showAge": UserMeta.MetaKeys.SHOW_AGE,
    "location": UserMeta.MetaKeys.LOCATION,
    "pmMail": UserMeta.MetaKeys.PM_MAIL,
    "newGameMail": UserMeta.MetaKeys.NEW_GAME_MAIL,
    "gmMail": UserMeta.MetaKeys.GM_MAIL,
}


@me.get("", response_model=schemas.UserOutput, response_model_exclude_none=True)
async def get_current_user(current_user: AuthedUser, full: bool = False):
    output = {
        "id": current_user.id,
        "username": current_user.username,
        "avatar": f"{configs.AVATARS_ROOT}/{current_user.avatar}",
    }
    if full:
        output["joinDate"] = current_user.join_date
        meta_by_key = {meta.key: meta.value for meta in current_user.meta}
        for field, key in _PROFILE_META_KEYS.items():
            output[field] = meta_by_key.get(key.value)
    return output


@me.post(
    "",
    response_model=schemas.UpdateProfileResponse,
    response_model_exclude_none=True,
)
async def update_current_user(
    profile: schemas.UpdateProfileInput,
    current_user: AuthedUser,
    db_session: DBSessionDependency,
):
    user_repo = UserRepository(db_session)

    updates = {}
    updated_fields = {}
    for field, key in _PROFILE_META_KEYS.items():
        if field not in profile.model_fields_set:
            continue
        value = getattr(profile, field)
        if value is None:
            continue
        updates[key] = value
        updated_fields[field] = value

    await user_repo.update_user_meta(current_user, updates)

    return {"success": True, "updated": updated_fields}


@me.post(
    "/avatar",
    response_model=schemas.UpdateAvatarResponse,
)
async def update_current_user_avatar(
    current_user: AuthedUser,
    db_session: DBSessionDependency,
    avatar: UploadFile = File(...),
):
    contents = await avatar.read()
    if len(contents) > AVATAR_MAX_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Avatar must be smaller than 5MB"
        )

    try:
        image = Image.open(io.BytesIO(contents))
        image.verify()
        image = Image.open(io.BytesIO(contents))
    except UnidentifiedImageError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is not a valid image")

    ext = _AVATAR_FORMAT_EXTENSIONS.get(image.format or "")
    if not ext:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Avatar must be a JPEG, PNG, or WEBP image"
        )

    image.thumbnail((AVATAR_MAX_DIMENSION, AVATAR_MAX_DIMENSION))
    if ext == "jpg" and image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    avatars_dir = Path(configs.AVATARS_DIR)
    old_ext = next(
        (
            meta.value
            for meta in current_user.meta
            if meta.key == UserMeta.MetaKeys.AVATAR_EXT.value
        ),
        None,
    )

    new_path = avatars_dir / f"{current_user.id}.{ext}"
    image.save(new_path, format=image.format)

    if old_ext and old_ext != ext:
        (avatars_dir / f"{current_user.id}.{old_ext}").unlink(missing_ok=True)

    user_repo = UserRepository(db_session)
    await user_repo.update_user_meta(current_user, {UserMeta.MetaKeys.AVATAR_EXT: ext})

    return {
        "success": True,
        "avatar": f"{configs.AVATARS_ROOT}/{current_user.id}.{ext}",
    }


@me.delete(
    "/avatar",
    response_model=schemas.DeleteAvatarResponse,
)
async def delete_current_user_avatar(
    current_user: AuthedUser,
    db_session: DBSessionDependency,
):
    user_repo = UserRepository(db_session)

    old_ext = next(
        (
            meta.value
            for meta in current_user.meta
            if meta.key == UserMeta.MetaKeys.AVATAR_EXT.value
        ),
        None,
    )
    if old_ext:
        avatars_dir = Path(configs.AVATARS_DIR)
        (avatars_dir / f"{current_user.id}.{old_ext}").unlink(missing_ok=True)

    await user_repo.delete_user_meta(current_user, UserMeta.MetaKeys.AVATAR_EXT)
    return {
        "success": True,
    }
