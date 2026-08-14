"""Thin async client for Cloudflare D1's HTTP REST API.

Containers can't use the native Workers `env.DB` binding, so D1 is reached
over HTTP instead. Credentials come from env vars set by the deploy pipeline.
"""
from __future__ import annotations

import os

import httpx

_API_BASE = "https://api.cloudflare.com/client/v4"


def _endpoint() -> str:
    account_id = os.environ["CF_ACCOUNT_ID"]
    database_id = os.environ["CF_D1_DATABASE_ID"]
    return f"{_API_BASE}/accounts/{account_id}/d1/database/{database_id}/query"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['CF_API_TOKEN']}",
        "Content-Type": "application/json",
    }


async def _run(sql: str, params: list | None = None) -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _endpoint(),
            headers=_headers(),
            json={"sql": sql, "params": params or []},
        )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(f"D1 query failed: {body.get('errors')}")
    results = body["result"]
    return results[0]["results"] if results else []


async def d1_query(sql: str, params: list | None = None) -> list[dict]:
    """Run a SELECT and return matching rows as dicts."""
    return await _run(sql, params)


async def d1_execute(sql: str, params: list | None = None) -> None:
    """Run an INSERT/UPDATE/DELETE."""
    await _run(sql, params)
