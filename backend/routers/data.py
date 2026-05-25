"""Data import endpoints: /api/data/*"""
from __future__ import annotations

import io
import os
from pathlib import Path

import pandas as pd
import pyreadstat
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from backend.schemas.data import DatasetPreview
from backend.services import column_inference, dataset_context, session_store
from regassist.ingest import load_file

router = APIRouter(prefix="/api/data", tags=["data"])

_SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample_data"
_SAMPLES = {
    "clean_wages": {"label": "Clean Wages", "file": "clean_wages.csv", "description": "Wage data for OLS regression"},
    "hetero_spending": {"label": "Hetero Spending", "file": "hetero_spending.csv", "description": "Spending data with heteroskedasticity"},
    "misspecified": {"label": "Misspecified Model", "file": "misspecified.csv", "description": "Dataset demonstrating model misspecification"},
    "multicollinear": {"label": "Multicollinear Data", "file": "multicollinear.csv", "description": "Dataset with multicollinearity"},
}


@router.post("/upload", response_model=DatasetPreview)
async def upload_file(file: UploadFile) -> DatasetPreview:
    raw = await file.read()
    filename = file.filename or "upload"

    try:
        if filename.lower().endswith(".sav"):
            df, _ = pyreadstat.read_sav(io.BytesIO(raw))
            # Build a minimal IngestResult-compatible response
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

    columns = column_inference.infer_columns(df, ingest.columns)
    context = dataset_context.infer_context(columns)
    session_id = session_store.create_session(df, filename)

    return DatasetPreview(
        session_id=session_id,
        filename=filename,
        row_count=ingest.row_count,
        columns=columns,
        dataset_context=context,
        warnings=ingest.warnings,
    )


@router.post("/paste", response_model=DatasetPreview)
async def paste_data(body: dict) -> DatasetPreview:
    text = body.get("text", "")
    if not text.strip():
        raise HTTPException(status_code=422, detail="No text provided.")

    # Detect delimiter: prefer tab if more tabs than commas per line
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
    columns = column_inference.infer_columns(df, ingest.columns)
    context = dataset_context.infer_context(columns)
    session_id = session_store.create_session(df, "pasted_data.csv")

    return DatasetPreview(
        session_id=session_id,
        filename="pasted_data.csv",
        row_count=len(df),
        columns=columns,
        dataset_context=context,
        warnings=ingest.warnings,
    )


@router.get("/samples")
async def list_samples() -> list[dict]:
    return [
        {"id": sid, "label": s["label"], "description": s["description"]}
        for sid, s in _SAMPLES.items()
        if (_SAMPLE_DIR / s["file"]).exists()
    ]


@router.get("/samples/{sample_id}", response_model=DatasetPreview)
async def load_sample(sample_id: str) -> DatasetPreview:
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
    columns = column_inference.infer_columns(df, ingest.columns)
    context = dataset_context.infer_context(columns)
    session_id = session_store.create_session(df, sample["file"])

    return DatasetPreview(
        session_id=session_id,
        filename=sample["file"],
        row_count=ingest.row_count,
        columns=columns,
        dataset_context=context,
        warnings=ingest.warnings,
    )
