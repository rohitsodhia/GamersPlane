import io
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

AVATAR_MAX_DIMENSION = 150
AVATAR_MAX_BYTES = 10 * 1024 * 1024
AVATAR_MAX_PIXELS = 25_000_000
AVATAR_FORMAT_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
READ_CHUNK_BYTES = 64 * 1024


def _too_large() -> HTTPException:
    return HTTPException(
        status.HTTP_400_BAD_REQUEST,
        f"Avatar must be smaller than {AVATAR_MAX_BYTES // (1024 * 1024)}MB",
    )


async def read_avatar_upload(upload: UploadFile) -> bytes:
    """Read an uploaded avatar, giving up as soon as it passes the size limit
    rather than buffering the whole body first."""
    body = bytearray()
    while chunk := await upload.read(READ_CHUNK_BYTES):
        body.extend(chunk)
        if len(body) > AVATAR_MAX_BYTES:
            raise _too_large()
    return bytes(body)


def process_avatar_upload(contents: bytes) -> tuple[Image.Image, str]:
    """Validate, resize, and normalize an uploaded avatar image.

    Returns the processed image and the file extension to save it under.
    Raises HTTPException(400) if the upload is too large, not a valid image,
    or not a supported format.
    """
    if len(contents) > AVATAR_MAX_BYTES:
        raise _too_large()

    invalid = HTTPException(status.HTTP_400_BAD_REQUEST, "File is not a valid image")
    try:
        image = Image.open(io.BytesIO(contents))
        # Width and height come from the header, so this rejects decompression
        # bombs before any pixel data is decoded.
        if image.width * image.height > AVATAR_MAX_PIXELS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Avatar must be smaller than {AVATAR_MAX_PIXELS // 1_000_000} megapixels",
            )
        image.verify()
        image = Image.open(io.BytesIO(contents))

        ext = AVATAR_FORMAT_EXTENSIONS.get(image.format or "")
        if not ext:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Avatar must be a JPEG, PNG, or WEBP image",
            )

        # thumbnail() is where the pixel data actually gets decoded, so a
        # truncated or corrupt file can still fail here.
        image.thumbnail((AVATAR_MAX_DIMENSION, AVATAR_MAX_DIMENSION))
        # Done after the thumbnail so only the small image gets rotated.
        # exif_transpose returns a copy that has lost its format, which
        # save_avatar needs.
        image_format = image.format
        image = ImageOps.exif_transpose(image)
        image.format = image_format
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        SyntaxError,
    ):
        raise invalid

    if ext == "jpg" and image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    return image, ext


def save_avatar(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format=image.format)
