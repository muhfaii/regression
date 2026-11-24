"""Data import endpoints: /api/data/*"""
from __future__ import annotations

import io
import os
from pathlib import Path

import pandas as pd
import pyreadstat
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from backend.middleware import get_current_user
from backend.models.user import User
from backend.schemas.data import DatasetPreview
from backend.services import column_inference, conversation_repo, dataset_context, limits, session_store
from regassist.ingest import load_file

router = APIRouter(prefix="/api/data", tags=["data"])


def _build_preview(df, ingest, filename, session_id, conversation_id=None):
    columns = column_inference.infer_columns(df, ingest.columns)
    context = dataset_context.infer_context(columns)
    return DatasetPreview(
        session_id=session_id,
        filename=filename,
        row_count=ingest.row_count,
        columns=columns,
        dataset_context=context,
        warnings=ingest.warnings,
        conversation_id=conversation_id,
    )

async def _require_own_conversation(conversation_id: str | None, user: User) -> None:
    if conversation_id and await conversation_repo.get_conversation(conversation_id, user.id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")


_SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample_data"
_SAMPLES = {
    "clean_wages": {"label": "Clean Wages", "file": "clean_wages.csv", "description": "Wage data for OLS regression"},
    "hetero_spending": {"label": "Hetero Spending", "file": "hetero_spending.csv", "description": "Spending data with heteroskedasticity"},
    "misspecified": {"label": "Misspecified Model", "file": "misspecified.csv", "description": "Dataset demonstrating model misspecification"},
    "multicollinear": {"label": "Multicollinear Data", "file": "multicollinear.csv", "description": "Dataset with multicollinearity"},
}


@router.post("/upload", response_model=DatasetPreview)
async def upload_file(
    file: UploadFile,
    conversation_id: str | None = None,
    current_user: User = Depends(get_current_user),
) -> DatasetPreview:
    await _require_own_conversation(conversation_id, current_user)
    raw = await limits.read_upload(file)
    filename = file.filename or "upload"

    try:
        if filename.lower().endswith(".sav"):
            df, _ = pyreadstat.read_sav(io.BytesIO(raw))
            from regassist.ingest import ColumnInfo as IngestColumnInfo, IngestResult
            cols = [
                IngestColumnInfo(
                    name=c,
                    dtype=str(df[c].dtype),
                    missing_count=int(df[c].isnull().sum()),
                    missing_pct=round(df[c].isnull().sum() / len(df) * 100, 2),
                )
                for c in df.columns
            ]
            ingest = IngestResult(df=df, row_count=len(df), columns=cols)
        else:
            ingest = load_file(raw, filename)
            df = ingest.df
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    session_id = session_store.create_session(
        df, filename, user_id=current_user.id, conversation_id=conversation_id
    )
    session_store.log_step(
        session_id, "Import",
        f"Imported '{filename}' ({ingest.row_count} rows, {len(ingest.columns)} columns).",
    )
    return _build_preview(df, ingest, filename, session_id, conversation_id)


@router.post("/paste", response_model=DatasetPreview)
async def paste_data(
    body: dict,
    conversation_id: str | None = None,
    current_user: User = Depends(get_current_user),
) -> DatasetPreview:
    await _require_own_conversation(conversation_id, current_user)
    text = body.get("text", "")
    if not text.strip():
        raise HTTPException(status_code=422, detail="No text provided.")
    if len(text) > limits.MAX_PASTE_CHARS:
        raise HTTPException(status_code=413, detail="Pasted data is too large.")

    lines = text.strip().splitlines()
    tab_count = sum(l.count("\t") for l in lines[:5])
    comma_count = sum(l.count(",") for l in lines[:5])
    sep = "\t" if tab_count >= comma_count else ","

    try:
        df = pd.read_csv(io.StringIO(text), sep=sep)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse pasted data: {exc}")

    if df.empty:
        raise HTTPException(status_code=422, detail="Pasted data contains no rows.")

    from regassist.ingest import ColumnInfo as IngestColumnInfo, IngestResult
    cols = [
        IngestColumnInfo(
            name=c,
            dtype=str(df[c].dtype),
            missing_count=int(df[c].isnull().sum()),
            missing_pct=round(df[c].isnull().sum() / len(df) * 100, 2),
        )
        for c in df.columns
    ]
    ingest = IngestResult(df=df, row_count=len(df), columns=cols)
    session_id = session_store.create_session(
        df, "pasted_data.csv", user_id=current_user.id, conversation_id=conversation_id
    )
    session_store.log_step(
        session_id, "Import",
        f"Imported pasted data ({ingest.row_count} rows, {len(ingest.columns)} columns).",
    )
    return _build_preview(df, ingest, "pasted_data.csv", session_id, conversation_id)


@router.get("/samples")
async def list_samples() -> list[dict]:
    return [
        {"id": sid, "label": s["label"], "description": s["description"]}
        for sid, s in _SAMPLES.items()
        if (_SAMPLE_DIR / s["file"]).exists()
    ]


@router.get("/samples/{sample_id}", response_model=DatasetPreview)
async def load_sample(
    sample_id: str,
    conversation_id: str | None = None,
    current_user: User = Depends(get_current_user),
) -> DatasetPreview:
    await _require_own_conversation(conversation_id, current_user)
    if sample_id not in _SAMPLES:
        raise HTTPException(status_code=404, detail="Sample not found.")

    sample = _SAMPLES[sample_id]
    path = _SAMPLE_DIR / sample["file"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample file not found on server.")

    try:
        ingest = load_file(str(path), sample["file"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    df = ingest.df
    session_id = session_store.create_session(
        df, sample["file"], user_id=current_user.id, conversation_id=conversation_id
    )
    session_store.log_step(
        session_id, "Import",
        f"Loaded sample dataset '{sample['label']}' ({ingest.row_count} rows, {len(ingest.columns)} columns).",
    )
    return _build_preview(df, ingest, sample["file"], session_id, conversation_id)
