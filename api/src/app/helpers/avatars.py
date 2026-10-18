from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from app.helpers.images import (
    IMAGE_FORMAT_EXTENSIONS,
    IMAGE_MAX_PIXELS,
    process_image_upload,
    read_image_upload,
    save_image,
)

AVATAR_MAX_DIMENSION = 150
AVATAR_MAX_BYTES = 10 * 1024 * 1024
AVATAR_MAX_PIXELS = IMAGE_MAX_PIXELS
AVATAR_FORMAT_EXTENSIONS = IMAGE_FORMAT_EXTENSIONS


async def read_avatar_upload(upload: UploadFile) -> bytes:
    return await read_image_upload(upload, AVATAR_MAX_BYTES, "Avatar")


def process_avatar_upload(contents: bytes) -> tuple[Image.Image, str]:
    return process_image_upload(
        contents,
        AVATAR_MAX_DIMENSION,
        AVATAR_MAX_BYTES,
        "Avatar",
        AVATAR_MAX_PIXELS,
    )


def save_avatar(image: Image.Image, path: Path) -> None:
    save_image(image, path)
