import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import HTTPException, status

from app.helpers.avatars import AVATAR_MAX_BYTES

FETCH_TIMEOUT_SECONDS = 10
MAX_REDIRECTS = 3


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, message)


async def ensure_public_host(host: str, port: int) -> None:
    """Raise a 400 unless ``host`` resolves only to globally routable addresses.

    Every resolved address must be public; one private answer is enough to reject,
    so a name can't mix a public and an internal record.

    Known gap: the HTTP client resolves the name again when it connects, so a
    DNS-rebinding host could answer differently the second time. Closing that
    means pinning the connection to the checked address; not worth it here.
    """
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        raise _bad_request("Could not resolve the image's host")

    if not infos:
        raise _bad_request("Could not resolve the image's host")

    for info in infos:
        # Drop an IPv6 zone id ("fe80::1%eth0") before parsing.
        address = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        if not address.is_global:
            raise _bad_request("That URL points to a private or internal address")


async def _validate_url(url: str) -> None:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise _bad_request("That is not a valid URL")

    if parts.scheme not in ("http", "https"):
        raise _bad_request("Image URL must start with http:// or https://")
    if not parts.hostname:
        raise _bad_request("That is not a valid URL")

    await ensure_public_host(
        parts.hostname, port or (443 if parts.scheme == "https" else 80)
    )


async def _fetch(
    url: str, max_bytes: int, transport: httpx.AsyncBaseTransport | None
) -> bytes:
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=False, transport=transport
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await _validate_url(url)
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise _bad_request("The image URL redirected without a target")
                    url = urljoin(url, location)
                    continue

                if response.status_code != 200:
                    raise _bad_request(
                        f"The image URL returned status {response.status_code}"
                    )

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise _bad_request("Image is too large")
                return bytes(body)

    raise _bad_request("The image URL redirected too many times")


async def fetch_remote_image(
    url: str,
    max_bytes: int = AVATAR_MAX_BYTES,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bytes:
    """Download an image from a user-supplied URL, guarding against SSRF.

    Only http/https, only public addresses, at most ``MAX_REDIRECTS`` redirects
    (each hop re-validated), a hard time limit, and a streamed size cap. The
    result still has to go through ``process_avatar_upload`` to be accepted.
    ``transport`` exists so tests can mock the network.
    """
    try:
        async with asyncio.timeout(FETCH_TIMEOUT_SECONDS):
            return await _fetch(url, max_bytes, transport)
    except TimeoutError:
        raise _bad_request("The image URL took too long to respond")
    except httpx.HTTPError:
        raise _bad_request("Could not download the image from that URL")
