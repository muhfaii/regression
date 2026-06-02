from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content_type: str
    payload: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: str
    title: str
    dataset_name: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = []

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    id: str
    title: str
    dataset_name: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class CreateConversationRequest(BaseModel):
    title: str | None = None
    dataset_name: str | None = None


class UpdateConversationRequest(BaseModel):
    title: str


class CreateMessageRequest(BaseModel):
    role: str = "user"
    content_type: str = "text"
    payload: dict = {}
