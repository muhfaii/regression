"""Export endpoints: /api/export/* — stub for Phase D."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/share/{result_id}")
async def create_share_link(result_id: str) -> dict:
    # Phase D implementation
    return {"url": None, "message": "Share links coming in Phase D."}
