"""Cloudflare R2 object storage, via its S3-compatible API.

Credentials come from env vars: CF_ACCOUNT_ID, R2_BUCKET,
R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY.
"""
from __future__ import annotations

import asyncio
import os
from functools import lru_cache

import boto3


@lru_cache(maxsize=1)
def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['CF_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _bucket() -> str:
    return os.environ["R2_BUCKET"]


async def put_object(key: str, data: bytes) -> None:
    await asyncio.to_thread(_client().put_object, Bucket=_bucket(), Key=key, Body=data)


async def get_object(key: str) -> bytes | None:
    def _get() -> bytes | None:
        try:
            return _client().get_object(Bucket=_bucket(), Key=key)["Body"].read()
        except _client().exceptions.NoSuchKey:
            return None

    return await asyncio.to_thread(_get)


async def delete_object(key: str) -> None:
    await asyncio.to_thread(_client().delete_object, Bucket=_bucket(), Key=key)
