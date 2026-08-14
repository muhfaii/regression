from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.models.conversation import Conversation, Message
from backend.services.d1 import d1_execute, d1_query


def _row_to_conversation(row: dict) -> Conversation:
    return Conversation(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        dataset_name=row["dataset_name"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_message(row: dict) -> Message:
    return Message(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=row["role"],
        content_type=row["content_type"],
        payload=row["payload"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


async def list_conversations_for_user(user_id: str) -> list[tuple[Conversation, int]]:
    rows = await d1_query(
        """SELECT c.*, COUNT(m.id) AS message_count
           FROM conversations c
           LEFT JOIN messages m ON m.conversation_id = c.id
           WHERE c.user_id = ?
           GROUP BY c.id
           ORDER BY c.updated_at DESC""",
        [user_id],
    )
    return [(_row_to_conversation(r), r["message_count"]) for r in rows]


async def create_conversation(user_id: str, title: str, dataset_name: str | None) -> Conversation:
    conv = Conversation(user_id=user_id, title=title, dataset_name=dataset_name)
    await d1_execute(
        """INSERT INTO conversations (id, user_id, title, dataset_name, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            conv.id, conv.user_id, conv.title, conv.dataset_name,
            conv.created_at.isoformat(), conv.updated_at.isoformat(),
        ],
    )
    return conv


async def get_conversation(conversation_id: str, user_id: str) -> Conversation | None:
    rows = await d1_query(
        "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
        [conversation_id, user_id],
    )
    return _row_to_conversation(rows[0]) if rows else None


async def update_conversation_title(conversation_id: str, title: str) -> None:
    await d1_execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
        [title, datetime.now(timezone.utc).isoformat(), conversation_id],
    )


async def touch_conversation(conversation_id: str) -> None:
    await d1_execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        [datetime.now(timezone.utc).isoformat(), conversation_id],
    )


async def delete_conversation(conversation_id: str) -> None:
    await d1_execute("DELETE FROM messages WHERE conversation_id = ?", [conversation_id])
    await d1_execute("DELETE FROM conversations WHERE id = ?", [conversation_id])


async def create_message(
    conversation_id: str, role: str, content_type: str, payload: dict
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content_type=content_type,
        payload=json.dumps(payload),
    )
    await d1_execute(
        """INSERT INTO messages (id, conversation_id, role, content_type, payload, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [msg.id, msg.conversation_id, msg.role, msg.content_type, msg.payload, msg.created_at.isoformat()],
    )
    await touch_conversation(conversation_id)
    return msg


async def list_messages(conversation_id: str) -> list[Message]:
    rows = await d1_query(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
        [conversation_id],
    )
    return [_row_to_message(r) for r in rows]
