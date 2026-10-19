import io

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.helpers.avatars import (
    AVATAR_MAX_BYTES,
    AVATAR_MAX_DIMENSION,
    process_avatar_upload,
    read_avatar_upload,
)


def _make_image_bytes(format="PNG", size=(10, 10)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color="red").save(buffer, format=format)
    return buffer.getvalue()


class TestProcessAvatarUpload:
    def test_resizes_images_larger_than_the_avatar_dimension(self):
        contents = _make_image_bytes(size=(AVATAR_MAX_DIMENSION * 3, 30))

        image, _ext = process_avatar_upload(contents)

        assert image.size == (AVATAR_MAX_DIMENSION, 10)


class TestReadAvatarUpload:
    async def test_rejects_uploads_over_the_avatar_limit(self):
        body = b"x" * (AVATAR_MAX_BYTES + 1)

        with pytest.raises(HTTPException) as exc_info:
            await read_avatar_upload(UploadFile(file=io.BytesIO(body)))

        assert exc_info.value.detail == "Avatar must be smaller than 10MB"
