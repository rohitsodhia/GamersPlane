import io

import pytest
from fastapi import HTTPException
from PIL import Image

from app.helpers.avatars import (
    AVATAR_MAX_BYTES,
    AVATAR_MAX_DIMENSION,
    process_avatar_upload,
)


def _make_image_bytes(format="PNG", size=(10, 10), mode="RGB", color="red"):
    buffer = io.BytesIO()
    Image.new(mode, size, color=color).save(buffer, format=format)
    return buffer.getvalue()


class TestProcessAvatarUpload:
    def test_rejects_oversized_uploads(self):
        oversized = b"0" * (AVATAR_MAX_BYTES + 1)

        with pytest.raises(HTTPException) as exc_info:
            process_avatar_upload(oversized)

        assert exc_info.value.status_code == 400

    def test_rejects_bytes_that_are_not_an_image(self):
        with pytest.raises(HTTPException) as exc_info:
            process_avatar_upload(b"not an image")

        assert exc_info.value.status_code == 400

    def test_rejects_an_unsupported_image_format(self):
        contents = _make_image_bytes(format="BMP")

        with pytest.raises(HTTPException) as exc_info:
            process_avatar_upload(contents)

        assert exc_info.value.status_code == 400

    def test_accepts_jpeg_png_and_webp(self):
        for format, expected_ext in [("JPEG", "jpg"), ("PNG", "png"), ("WEBP", "webp")]:
            contents = _make_image_bytes(format=format)

            _image, ext = process_avatar_upload(contents)

            assert ext == expected_ext

    def test_resizes_images_larger_than_the_max_dimension(self):
        contents = _make_image_bytes(size=(AVATAR_MAX_DIMENSION * 3, 10))

        image, _ext = process_avatar_upload(contents)

        assert max(image.size) <= AVATAR_MAX_DIMENSION

    def test_leaves_smaller_images_unresized(self):
        contents = _make_image_bytes(size=(10, 20))

        image, _ext = process_avatar_upload(contents)

        assert image.size == (10, 20)

    def test_converts_rgba_to_rgb_when_saving_as_jpg(self):
        contents = _make_image_bytes(format="PNG", mode="RGBA")

        image, ext = process_avatar_upload(contents)

        # The source is a PNG, so no jpg conversion should happen here.
        assert ext == "png"
        assert image.mode == "RGBA"

    def test_converts_rgba_jpeg_source_to_rgb(self, monkeypatch):
        # A real JPEG file can never decode to RGBA/P mode (the format has no
        # alpha/palette support), so the only way to exercise this branch is
        # to force an RGBA image's reported format to JPEG.
        contents = _make_image_bytes(format="PNG", mode="RGBA")
        real_open = Image.open

        def fake_open(fp):
            image = real_open(fp)
            image.format = "JPEG"
            return image

        monkeypatch.setattr(Image, "open", fake_open)

        image, ext = process_avatar_upload(contents)

        assert ext == "jpg"
        assert image.mode == "RGB"
