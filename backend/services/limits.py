"""Request size limits and in-memory rate limiting.

The rate limiter keeps state in process memory, which is correct for the
single uvicorn process the backend runs as. Multiple processes or instances
would each keep their own counts.
"""
from __future__ import annotations

import time
from collections import deque

from fastapi import HTTPException, Request, UploadFile, status

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_PASTE_CHARS = 20 * 1024 * 1024


async def read_upload(file: UploadFile) -> bytes:
    """Read an uploaded file, rejecting it if it exceeds MAX_UPLOAD_BYTES."""
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )
    return raw


class RateLimiter:
    """Sliding-window limiter: at most `max_calls` per `window` seconds per key."""

    def __init__(self, max_calls: int, window: float) -> None:
        self.max_calls = max_calls
        self.window = window
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str) -> None:
        """Record a call for `key`; raise 429 if the key is over its limit."""
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.max_calls:
            retry_after = int(hits[0] + self.window - now) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)


login_by_email = RateLimiter(max_calls=10, window=15 * 60)
login_by_ip = RateLimiter(max_calls=30, window=15 * 60)
register_by_ip = RateLimiter(max_calls=5, window=60 * 60)
chat_by_user = RateLimiter(max_calls=30, window=10 * 60)


def client_ip(request: Request) -> str:
    """Best-effort client IP.

    The Cloudflare Worker forwards the visitor's IP in X-Infera-Client-IP;
    requests that reach the backend directly fall back to the socket peer.
    """
    forwarded = request.headers.get("x-infera-client-ip")
    if forwarded:
        return forwarded.strip()
    return request.client.host if request.client else "unknown"
