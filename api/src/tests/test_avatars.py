import io
import os

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.helpers.avatars import (
    AVATAR_MAX_BYTES,
    AVATAR_MAX_DIMENSION,
    AVATAR_MAX_PIXELS,
    READ_CHUNK_BYTES,
    process_avatar_upload,
    read_avatar_upload,
)


class _CountingFile(io.BytesIO):
    def __init__(self, data: bytes):
        super().__init__(data)
        self.bytes_read = 0

    def read(self, size=-1):
        chunk = super().read(size)
        self.bytes_read += len(chunk)
        return chunk


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
        assert exc_info.value.detail == "Avatar must be smaller than 10MB"

    def test_rejects_bytes_that_are_not_an_image(self):
        with pytest.raises(HTTPException) as exc_info:
            process_avatar_upload(b"not an image")

        assert exc_info.value.status_code == 400

    def test_rejects_an_unsupported_image_format(self):
        contents = _make_image_bytes(format="BMP")

        with pytest.raises(HTTPException) as exc_info:
            process_avatar_upload(contents)

        assert exc_info.value.status_code == 400

    @pytest.mark.parametrize(
        ("format", "expected_ext"), [("JPEG", "jpg"), ("PNG", "png"), ("WEBP", "webp")]
    )
    def test_accepts_jpeg_png_and_webp(self, format, expected_ext):
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

    def test_png_with_alpha_keeps_its_alpha_channel(self):
        contents = _make_image_bytes(format="PNG", mode="RGBA")

        image, ext = process_avatar_upload(contents)

        # The source is a PNG, so no jpg conversion should happen here.
        assert ext == "png"
        assert image.mode == "RGBA"

    def test_rejects_images_over_the_pixel_limit(self):
        # Mode "1" keeps the file tiny while still having > AVATAR_MAX_PIXELS pixels.
        contents = _make_image_bytes(size=(6000, 5000), mode="1")
        assert 6000 * 5000 > AVATAR_MAX_PIXELS

        with pytest.raises(HTTPException) as exc_info:
            process_avatar_upload(contents)

        assert exc_info.value.status_code == 400
        assert "megapixels" in exc_info.value.detail

    def test_rejects_decompression_bombs_with_a_400(self):
        # Large enough that Pillow itself raises DecompressionBombError on open,
        # before our own pixel check runs.
        contents = _make_image_bytes(size=(15000, 15000), mode="1")

        with pytest.raises(HTTPException) as exc_info:
            process_avatar_upload(contents)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "File is not a valid image"

    def test_rejects_truncated_images_with_a_400(self):
        noise = Image.frombytes("RGB", (200, 200), os.urandom(200 * 200 * 3))
        buffer = io.BytesIO()
        noise.save(buffer, format="PNG")
        contents = buffer.getvalue()

        with pytest.raises(HTTPException) as exc_info:
            process_avatar_upload(contents[: len(contents) // 2])

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "File is not a valid image"

    def test_rejects_images_that_fail_while_decoding(self):
        # JPEG's verify() doesn't check the scan data, so a file cut off mid-scan
        # passes it and only fails when thumbnail() decodes it.
        noise = Image.frombytes("RGB", (300, 300), os.urandom(300 * 300 * 3))
        buffer = io.BytesIO()
        noise.save(buffer, format="JPEG")
        contents = buffer.getvalue()

        with pytest.raises(HTTPException) as exc_info:
            process_avatar_upload(contents[: len(contents) * 6 // 10])

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "File is not a valid image"

    def test_applies_exif_orientation(self):
        source = Image.new("RGB", (40, 20), color="red")
        exif = Image.Exif()
        exif[0x0112] = 6  # rotated a quarter turn, so width and height swap
        buffer = io.BytesIO()
        source.save(buffer, format="JPEG", exif=exif)

        image, ext = process_avatar_upload(buffer.getvalue())

        assert image.size == (20, 40)
        # The transposed copy must keep its format or save_avatar writes nothing.
        assert image.format == "JPEG"
        assert ext == "jpg"

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


class TestReadAvatarUpload:
    async def test_returns_the_whole_body_when_within_the_limit(self):
        body = b"x" * (READ_CHUNK_BYTES * 2 + 5)

        result = await read_avatar_upload(UploadFile(file=io.BytesIO(body)))

        assert result == body

    async def test_rejects_oversize_uploads_without_reading_them_all(self):
        file = _CountingFile(b"x" * (AVATAR_MAX_BYTES * 3))

        with pytest.raises(HTTPException) as exc_info:
            await read_avatar_upload(UploadFile(file=file))

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Avatar must be smaller than 10MB"
        assert file.bytes_read <= AVATAR_MAX_BYTES + READ_CHUNK_BYTES
