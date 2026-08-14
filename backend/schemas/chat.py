from __future__ import annotations

from pydantic import BaseModel

from backend.schemas.conversation import MessageResponse


class ChatRequest(BaseModel):
    conversation_id: str
    message: str


class ChatResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
