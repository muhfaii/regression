"""Chat endpoint — POST /api/chat"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status

from backend.middleware import get_current_user
from backend.models.user import User
from backend.schemas.chat import ChatRequest, ChatResponse
from backend.schemas.conversation import MessageResponse
from backend.services import conversation_repo, llm as llm_service, session_store
from backend.services.column_inference import _classify_type

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/config")
async def chat_config():
    return {
        "configured": llm_service.is_configured(),
        "model": llm_service.get_model_name(),
    }


def _to_msg_response(msg) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content_type=msg.content_type,
        payload=json.loads(msg.payload) if isinstance(msg.payload, str) else msg.payload,
        created_at=msg.created_at,
    )


def _build_session_info(conv_id: str) -> dict | None:
    session = session_store.find_session_for_conversation(conv_id)
    if session is None:
        return None
    df = session.df
    columns = []
    for col in df.columns:
        try:
            inferred = _classify_type(df[col])
        except Exception:
            inferred = str(df[col].dtype)
        columns.append({
            "name": col,
            "raw_dtype": str(df[col].dtype),
            "inferred_type": inferred,
        })
    return {
        "filename": session.filename,
        "row_count": len(df),
        "columns": columns,
        "dataset_context": "survey" if any(
            c["inferred_type"] == "categorical" for c in columns
        ) else "generic",
    }


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    conv = await conversation_repo.get_conversation(req.conversation_id, current_user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    messages = await conversation_repo.list_messages(req.conversation_id)

    if not llm_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM is not configured. Set LLM_API_KEY environment variable.",
        )

    # Store user message
    user_msg = await conversation_repo.create_message(
        req.conversation_id, "user", "text", {"text": req.message}
    )

    # Build context and call LLM
    session_info = _build_session_info(req.conversation_id)
    all_messages = list(messages) + [user_msg]
    try:
        llm_text = await llm_service.generate_chat_response(all_messages, session_info)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Parse LLM response for action chips
    payload: dict = {"text": llm_text}
    if "[ACTION:" in llm_text:
        for keyword in ["guide", "browse", "data"]:
            if f"[ACTION:{keyword}]" in llm_text:
                payload.setdefault("actions", []).append(keyword)
    llm_text_clean = llm_text
    for keyword in ["guide", "browse", "data"]:
        llm_text_clean = llm_text_clean.replace(f"[ACTION:{keyword}]", "")
    payload["text"] = llm_text_clean.strip()

    # Store assistant message
    assistant_msg = await conversation_repo.create_message(
        req.conversation_id, "assistant", "text", payload
    )

    return ChatResponse(
        user_message=_to_msg_response(user_msg),
        assistant_message=_to_msg_response(assistant_msg),
    )
