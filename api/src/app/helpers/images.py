import io
import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

IMAGE_MAX_PIXELS = 25_000_000
IMAGE_FORMAT_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
READ_CHUNK_BYTES = 64 * 1024


def _too_large(max_bytes: int, label: str) -> HTTPException:
    return HTTPException(
        status.HTTP_400_BAD_REQUEST,
        f"{label} must be smaller than {max_bytes // (1024 * 1024)}MB",
    )


async def read_image_upload(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    """Read an uploaded image, giving up as soon as it passes the size limit
    rather than buffering the whole body first."""
    body = bytearray()
    while chunk := await upload.read(READ_CHUNK_BYTES):
        body.extend(chunk)
        if len(body) > max_bytes:
            raise _too_large(max_bytes, label)
    return bytes(body)


def process_image_upload(
    contents: bytes,
    max_dimension: int,
    max_bytes: int,
    label: str,
    max_pixels: int = IMAGE_MAX_PIXELS,
) -> tuple[Image.Image, str]:
    """Validate, resize, and normalize an uploaded image.

    Returns the processed image and the file extension to save it under.
    Raises HTTPException(400) if the upload is too large, not a valid image,
    or not a supported format.
    """
    if len(contents) > max_bytes:
        raise _too_large(max_bytes, label)

    invalid = HTTPException(status.HTTP_400_BAD_REQUEST, "File is not a valid image")
    try:
        image = Image.open(io.BytesIO(contents))
        # Width and height come from the header, so this rejects decompression
        # bombs before any pixel data is decoded.
        if image.width * image.height > max_pixels:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{label} must be smaller than {max_pixels // 1_000_000} megapixels",
            )
        image.verify()
        image = Image.open(io.BytesIO(contents))

        ext = IMAGE_FORMAT_EXTENSIONS.get(image.format or "")
        if not ext:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{label} must be a JPEG, PNG, or WEBP image",
            )

        # thumbnail() is where the pixel data actually gets decoded, so a
        # truncated or corrupt file can still fail here.
        image.thumbnail((max_dimension, max_dimension))
        # Done after the thumbnail so only the small image gets rotated.
        # exif_transpose returns a copy that has lost its format, which
        # save_image needs.
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


def quarantine_image(src: Path, dest: Path, *, move: bool) -> bool:
    """Copy (or, with ``move``, move) an image into quarantine, making ``dest``'s
    folders. Returns False, touching nothing, if ``src`` is missing."""
    if not src.is_file():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    if move:
        shutil.move(src, dest)
    else:
        shutil.copy2(src, dest)
    return True


def save_image(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format=image.format)
