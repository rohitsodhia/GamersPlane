import socket

import httpx
import pytest
from fastapi import HTTPException

from app.helpers import remote_image
from app.helpers.remote_image import ensure_public_host, fetch_remote_image

PUBLIC_IP = "93.184.216.34"
PUBLIC_URL = f"http://{PUBLIC_IP}/pic.png"


class TestEnsurePublicHost:
    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1",
            "localhost",
            "10.1.2.3",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "0.0.0.0",
            "::1",
            "fe80::1",
            "fd00::1",
            "::ffff:127.0.0.1",
        ],
    )
    async def test_non_public_addresses_are_rejected(self, host):
        with pytest.raises(HTTPException) as exc_info:
            await ensure_public_host(host, 80)

        assert exc_info.value.status_code == 400

    async def test_a_public_address_passes(self):
        await ensure_public_host(PUBLIC_IP, 80)

    async def test_one_private_answer_among_public_ones_is_rejected(self, monkeypatch):
        answers = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 80)),
        ]
        monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: answers)

        with pytest.raises(HTTPException) as exc_info:
            await ensure_public_host("mixed.example", 80)

        assert exc_info.value.status_code == 400

    async def test_an_unresolvable_host_is_a_400(self, monkeypatch):
        def fail(*args, **kwargs):
            raise socket.gaierror("nope")

        monkeypatch.setattr(socket, "getaddrinfo", fail)

        with pytest.raises(HTTPException) as exc_info:
            await ensure_public_host("missing.example", 80)

        assert exc_info.value.status_code == 400


def serving(handler):
    return httpx.MockTransport(handler)


async def fetch_status(url, transport, **kwargs):
    with pytest.raises(HTTPException) as exc_info:
        await fetch_remote_image(url, transport=transport, **kwargs)
    assert exc_info.value.status_code == 400
    return exc_info.value.detail


class TestFetchRemoteImage:
    async def test_returns_the_body(self):
        transport = serving(lambda request: httpx.Response(200, content=b"bytes"))

        assert await fetch_remote_image(PUBLIC_URL, transport=transport) == b"bytes"

    @pytest.mark.parametrize(
        "url", ["ftp://example.com/a.png", "file:///etc/passwd", "//example.com/a.png"]
    )
    async def test_only_http_and_https_are_allowed(self, url):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, content=b"x")

        await fetch_status(url, serving(handler))

        assert requests == []

    @pytest.mark.parametrize(
        "url",
        ["http://127.0.0.1/a.png", "http://[::1]/a.png", "http://10.0.0.5:8080/a.png"],
    )
    async def test_private_targets_are_never_requested(self, url):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, content=b"x")

        await fetch_status(url, serving(handler))

        assert requests == []

    async def test_non_200_is_a_400(self):
        await fetch_status(PUBLIC_URL, serving(lambda r: httpx.Response(404)))

    async def test_a_redirect_is_followed_and_resolved_against_the_current_url(self):
        def handler(request):
            if request.url.path == "/pic.png":
                return httpx.Response(302, headers={"location": "/real.png"})
            return httpx.Response(200, content=b"final")

        result = await fetch_remote_image(PUBLIC_URL, transport=serving(handler))

        assert result == b"final"

    async def test_a_redirect_to_a_private_address_is_blocked(self):
        requests = []

        def handler(request):
            requests.append(str(request.url))
            return httpx.Response(
                302, headers={"location": "http://169.254.169.254/latest/meta-data"}
            )

        await fetch_status(PUBLIC_URL, serving(handler))

        assert requests == [PUBLIC_URL]

    async def test_at_most_three_redirects_are_followed(self):
        def handler(request):
            hop = int(request.url.path.removeprefix("/hop") or 0)
            return httpx.Response(302, headers={"location": f"/hop{hop + 1}"})

        await fetch_status(f"http://{PUBLIC_IP}/hop0", serving(handler))

    async def test_three_redirects_then_a_body_is_fine(self):
        def handler(request):
            hop = int(request.url.path.removeprefix("/hop") or 0)
            if hop == 3:
                return httpx.Response(200, content=b"ok")
            return httpx.Response(302, headers={"location": f"/hop{hop + 1}"})

        result = await fetch_remote_image(
            f"http://{PUBLIC_IP}/hop0", transport=serving(handler)
        )

        assert result == b"ok"

    async def test_a_redirect_without_a_target_is_a_400(self):
        await fetch_status(PUBLIC_URL, serving(lambda r: httpx.Response(302)))

    async def test_a_body_over_the_cap_is_aborted(self):
        transport = serving(lambda request: httpx.Response(200, content=b"x" * 50))

        await fetch_status(PUBLIC_URL, transport, max_bytes=10)

    async def test_a_transport_failure_is_a_400(self):
        def handler(request):
            raise httpx.ConnectError("refused")

        await fetch_status(PUBLIC_URL, serving(handler))

    async def test_a_slow_response_is_cut_off(self, monkeypatch):
        import asyncio

        async def slow(url, max_bytes, transport):
            await asyncio.sleep(5)

        monkeypatch.setattr(remote_image, "FETCH_TIMEOUT_SECONDS", 0.05)
        monkeypatch.setattr(remote_image, "_fetch", slow)

        detail = await fetch_status(PUBLIC_URL, None)

        assert "too long" in detail
