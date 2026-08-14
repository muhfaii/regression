from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.services.d1 import d1_execute, d1_query


async def save_share(token: str, result: dict) -> None:
    await d1_execute(
        "INSERT INTO share_tokens (token, payload, created_at) VALUES (?, ?, ?)",
        [token, json.dumps(result, default=str), datetime.now(timezone.utc).isoformat()],
    )


async def get_share(token: str) -> dict | None:
    rows = await d1_query("SELECT payload FROM share_tokens WHERE token = ?", [token])
    return json.loads(rows[0]["payload"]) if rows else None
