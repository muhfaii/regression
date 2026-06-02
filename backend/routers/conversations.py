from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware import get_current_user
from backend.models.conversation import Conversation, Message
from backend.models.user import User
from backend.schemas.conversation import (
    ConversationListItem,
    ConversationResponse,
    CreateConversationRequest,
    CreateMessageRequest,
    MessageResponse,
    UpdateConversationRequest,
)


def _auto_title(dataset_name: str | None) -> str:
    date_part = datetime.now(timezone.utc).strftime("%d-%m-%y")
    prefix = dataset_name or "New analysis"
    return f"{prefix} - {date_part}"

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConversationListItem]:
    stmt = (
        select(
            Conversation,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == current_user.id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for conv, msg_count in rows:
        item = ConversationListItem(
            id=conv.id,
            title=conv.title,
            dataset_name=conv.dataset_name,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=msg_count,
        )
        items.append(item)

    return items


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    title = body.title or _auto_title(body.dataset_name)
    conv = Conversation(
        user_id=current_user.id,
        title=title,
        dataset_name=body.dataset_name,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    conv.title = body.title
    await db.commit()
    await db.refresh(conv)

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg = Message(
        conversation_id=conversation_id,
        role=body.role,
        content_type=body.content_type,
        payload=json.dumps(body.payload),
    )
    db.add(msg)
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)

    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content_type=msg.content_type,
        payload=json.loads(msg.payload) if isinstance(msg.payload, str) else msg.payload,
        created_at=msg.created_at,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        dataset_name=conv.dataset_name,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content_type=m.content_type,
            payload=json.loads(m.payload) if isinstance(m.payload, str) else m.payload,
            created_at=m.created_at,
        ) for m in messages],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    await db.delete(conv)
    await db.commit()
