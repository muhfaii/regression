"""Data preparation endpoints: /api/dataprep/*"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from backend.middleware import get_current_user
from backend.models.user import User
from backend.schemas.data import DatasetPreview
from backend.schemas.dataprep import (
    ComputeRequest,
    MissingDataRequest,
    RecodeRequest,
    ReverseScoreRequest,
)
from backend.services import column_inference, dataprep, dataset_context, limits, session_store
from backend.services.session_store import Session
from regassist.ingest import _collect_warnings, _describe_column, load_file

router = APIRouter(prefix="/api/dataprep", tags=["dataprep"])


async def _get_session_or_404(session_id: str, user: User) -> Session:
    session = await session_store.get_owned_session(session_id, user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    return session


async def _apply_and_respond(session: Session, session_id: str, new_df, message: str) -> DatasetPreview:
    await session_store.update_session_df(session_id, new_df)
    await session_store.log_step(session_id, "Data prep", message)
    ingest_cols = [_describe_column(new_df[c], len(new_df)) for c in new_df.columns]
    columns = column_inference.infer_columns(new_df, ingest_cols)
    context = dataset_context.infer_context(columns)
    return DatasetPreview(
        session_id=session_id,
        filename=session.filename,
        row_count=len(new_df),
        columns=columns,
        dataset_context=context,
        warnings=[message, *_collect_warnings(ingest_cols)],
        conversation_id=session.conversation_id,
    )


@router.post("/missing", response_model=DatasetPreview)
async def apply_missing(req: MissingDataRequest, current_user: User = Depends(get_current_user)) -> DatasetPreview:
    session = await _get_session_or_404(req.session_id, current_user)
    try:
        new_df, message = dataprep.apply_missing_strategy(session.df, req.columns, req.strategy, req.constant)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return await _apply_and_respond(session, req.session_id, new_df, message)


@router.post("/recode", response_model=DatasetPreview)
async def recode(req: RecodeRequest, current_user: User = Depends(get_current_user)) -> DatasetPreview:
    session = await _get_session_or_404(req.session_id, current_user)
    try:
        new_df, message = dataprep.recode_column(
            session.df, req.source_column, req.new_column_name, req.mapping, req.default, req.overwrite,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return await _apply_and_respond(session, req.session_id, new_df, message)


@router.post("/compute", response_model=DatasetPreview)
async def compute(req: ComputeRequest, current_user: User = Depends(get_current_user)) -> DatasetPreview:
    session = await _get_session_or_404(req.session_id, current_user)
    try:
        new_df, message = dataprep.compute_column(
            session.df, req.new_column_name, req.expression, req.overwrite,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return await _apply_and_respond(session, req.session_id, new_df, message)


@router.post("/reverse-score", response_model=DatasetPreview)
async def reverse_score(req: ReverseScoreRequest, current_user: User = Depends(get_current_user)) -> DatasetPreview:
    session = await _get_session_or_404(req.session_id, current_user)
    try:
        new_df, message = dataprep.reverse_score(
            session.df, req.columns, req.min_value, req.max_value, req.suffix, req.overwrite,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return await _apply_and_respond(session, req.session_id, new_df, message)


@router.post("/merge", response_model=DatasetPreview)
async def merge(
    session_id: str = Form(...),
    left_on: str = Form(...),
    right_on: str = Form(...),
    how: str = Form("left"),
    file: UploadFile = None,
    current_user: User = Depends(get_current_user),
) -> DatasetPreview:
    session = await _get_session_or_404(session_id, current_user)
    if file is None:
        raise HTTPException(status_code=422, detail="A file to merge is required.")

    raw = await limits.read_upload(file)
    try:
        ingest = load_file(raw, file.filename or "merge_upload.csv")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        new_df, message = dataprep.merge_datasets(session.df, ingest.df, left_on, right_on, how)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return await _apply_and_respond(session, session_id, new_df, message)
