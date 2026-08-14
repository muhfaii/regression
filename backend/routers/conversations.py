from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from backend.middleware import get_current_user
from backend.models.user import User
from backend.schemas.conversation import (
    ConversationListItem,
    ConversationResponse,
    CreateConversationRequest,
    CreateMessageRequest,
    MessageResponse,
    UpdateConversationRequest,
)
from backend.services import conversation_repo


def _auto_title(dataset_name: str | None) -> str:
    date_part = datetime.now(timezone.utc).strftime("%d-%m-%y")
    prefix = dataset_name or "New analysis"
    return f"{prefix} - {date_part}"


def _to_msg_response(msg) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content_type=msg.content_type,
        payload=json.loads(msg.payload) if isinstance(msg.payload, str) else msg.payload,
        created_at=msg.created_at,
    )


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    current_user: User = Depends(get_current_user),
) -> list[ConversationListItem]:
    rows = await conversation_repo.list_conversations_for_user(current_user.id)
    return [
        ConversationListItem(
            id=conv.id,
            title=conv.title,
            dataset_name=conv.dataset_name,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=msg_count,
        )
        for conv, msg_count in rows
    ]


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    title = body.title or _auto_title(body.dataset_name)
    conv = await conversation_repo.create_conversation(current_user.id, title, body.dataset_name)

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        dataset_name=conv.dataset_name,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[],
    )


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    body: UpdateConversationRequest,
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    conv = await conversation_repo.get_conversation(conversation_id, current_user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    await conversation_repo.update_conversation_title(conversation_id, body.title)
    conv = await conversation_repo.get_conversation(conversation_id, current_user.id)

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        dataset_name=conv.dataset_name,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    conversation_id: str,
    body: CreateMessageRequest,
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    conv = await conversation_repo.get_conversation(conversation_id, current_user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg = await conversation_repo.create_message(
        conversation_id, body.role, body.content_type, body.payload
    )

    return _to_msg_response(msg)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    conv = await conversation_repo.get_conversation(conversation_id, current_user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    messages = await conversation_repo.list_messages(conversation_id)

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        dataset_name=conv.dataset_name,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[_to_msg_response(m) for m in messages],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    conv = await conversation_repo.get_conversation(conversation_id, current_user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    await conversation_repo.delete_conversation(conversation_id)
