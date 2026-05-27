"""Export endpoints: /api/export/* and public /api/share/*"""
from __future__ import annotations

import dataclasses
import io
import uuid

from docx import Document
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.services import session_store

router = APIRouter(tags=["export"])

_SKIP_STAT_KEYS = frozenset({
    "variables", "groups", "coefficients", "post_hoc",
    "contingency_table", "outcome_categories",
})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/export/word/{result_id}")
async def export_word(result_id: str, session_id: str) -> StreamingResponse:
    raw = session_store.get_result(session_id, result_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Result not found.")

    result = _normalize(raw)
    doc = _build_docx(result)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    filename = f"{result.get('test_key', 'result')}_{result_id[:8]}.docx"
    return StreamingResponse(
        buf,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/export/share/{result_id}")
async def create_share_link(result_id: str, session_id: str) -> dict:
    raw = session_store.get_result(session_id, result_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Result not found.")

    token = str(uuid.uuid4())
    session_store.save_share(token, raw)
    return {"token": token, "url": f"/share/{token}"}


@router.get("/api/share/{token}")
async def get_shared_result(token: str) -> dict:
    raw = session_store.get_share(token)
    if raw is None:
        raise HTTPException(status_code=404, detail="Share link not found.")
    return _normalize(raw)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(result: dict) -> dict:
    """Convert nested dataclass instances in a stored result dict to plain dicts."""
    out: dict = {}
    for k, v in result.items():
        if dataclasses.is_dataclass(v) and not isinstance(v, type):
            out[k] = dataclasses.asdict(v)
        elif isinstance(v, list):
            out[k] = [
                dataclasses.asdict(i) if dataclasses.is_dataclass(i) and not isinstance(i, type) else i
                for i in v
            ]
        else:
            out[k] = v
    return out


def _fmt(val: object) -> str:
    if isinstance(val, float):
        return f"{val:.4f}"
    if isinstance(val, bool):
        return "Yes" if val else "No"
    return str(val)


def _build_docx(result: dict) -> Document:
    doc = Document()

    # Title + N
    doc.add_heading(result.get("test_name", "Analysis"), 0)
    doc.add_paragraph(f"N = {result.get('n_obs', '—')}")

    # Key scalar statistics table
    stats = result.get("statistics", {})
    scalar_stats = {
        k: v for k, v in stats.items()
        if k not in _SKIP_STAT_KEYS and isinstance(v, (int, float, str, bool))
    }
    if scalar_stats:
        doc.add_heading("Statistics", level=1)
        tbl = doc.add_table(rows=1, cols=2)
        tbl.style = "Table Grid"
        hdr = tbl.rows[0].cells
        hdr[0].text = "Statistic"
        hdr[1].text = "Value"
        for key, val in scalar_stats.items():
            row = tbl.add_row().cells
            row[0].text = key.replace("_", " ").title()
            row[1].text = _fmt(val)

    # Effect size
    effect = result.get("effect_size")
    if effect:
        doc.add_heading("Effect Size", level=1)
        doc.add_paragraph(
            f"{effect['name']}: {effect['value']:.3f} ({effect['interpretation']})"
        )

    # Assumption checks
    checks = result.get("assumption_checks", [])
    if checks:
        doc.add_heading("Assumption Checks", level=1)
        icons = {"pass": "✓", "amber": "⚠", "fail": "✗"}
        for check in checks:
            icon = icons.get(check.get("status", ""), "")
            doc.add_paragraph(f"{icon} {check['name']}: {check['detail']}")
            if check.get("fix_suggestion"):
                doc.add_paragraph(f"Suggestion: {check['fix_suggestion']}")

    # Interpretation — APA first (most useful for export), then plain English
    interp = result.get("interpretation", {})
    if interp:
        doc.add_heading("Interpretation", level=1)
        doc.add_heading("APA 7", level=2)
        doc.add_paragraph(interp.get("apa", ""))
        doc.add_heading("Plain English", level=2)
        doc.add_paragraph(interp.get("plain", ""))

    return doc
