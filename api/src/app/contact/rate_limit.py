import time
from collections import defaultdict, deque

from fastapi import Request

RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW_SECONDS = 60 * 60

# Per-process and in-memory: a restart (or another worker) resets it, which is
# acceptable for a low-traffic contact form.
_hits: defaultdict[str, deque[float]] = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def client_ip(request: Request) -> str:
    """The address nginx saw. It appends the real client to X-Forwarded-For, so the
    rightmost entry is trustworthy; anything to its left is client-supplied."""
    forwarded = request.headers.get("x-forwarded-for", "")
    rightmost = forwarded.split(",")[-1].strip()
    if rightmost:
        return rightmost
    return request.client.host if request.client else "unknown"


def allow(ip: str) -> bool:
    """Record a submission from `ip` and return False if it exceeds the limit."""
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS

    # Drop expired entries everywhere so idle addresses don't accumulate.
    for key in list(_hits):
        hits = _hits[key]
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if not hits:
            del _hits[key]

    hits = _hits[ip]
    if len(hits) >= RATE_LIMIT_MAX:
        return False
    hits.append(now)
    return True
