from __future__ import annotations

from datetime import datetime

from backend.models.user import User
from backend.services.d1 import d1_execute, d1_query


def _row_to_user(row: dict) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        display_name=row["display_name"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


async def get_user_by_id(user_id: str) -> User | None:
    rows = await d1_query("SELECT * FROM users WHERE id = ?", [user_id])
    return _row_to_user(rows[0]) if rows else None


async def get_user_by_email(email: str) -> User | None:
    rows = await d1_query("SELECT * FROM users WHERE email = ?", [email])
    return _row_to_user(rows[0]) if rows else None


async def create_user(email: str, password_hash: str, display_name: str) -> User:
    user = User(email=email, password_hash=password_hash, display_name=display_name)
    await d1_execute(
        """INSERT INTO users (id, email, password_hash, display_name, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            user.id, user.email, user.password_hash, user.display_name,
            user.created_at.isoformat(), user.updated_at.isoformat(),
        ],
    )
    return user
