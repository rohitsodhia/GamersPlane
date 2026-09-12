import io
from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError

AVATAR_MAX_DIMENSION = 150
AVATAR_MAX_BYTES = 5 * 1024 * 1024
AVATAR_FORMAT_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


def process_avatar_upload(contents: bytes) -> tuple[Image.Image, str]:
    """Validate, resize, and normalize an uploaded avatar image.

    Returns the processed image and the file extension to save it under.
    Raises HTTPException(400) if the upload is too large, not a valid image,
    or not a supported format.
    """
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

    ext = AVATAR_FORMAT_EXTENSIONS.get(image.format or "")
    if not ext:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Avatar must be a JPEG, PNG, or WEBP image"
        )

    image.thumbnail((AVATAR_MAX_DIMENSION, AVATAR_MAX_DIMENSION))
    if ext == "jpg" and image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    return image, ext


def save_avatar(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format=image.format)
