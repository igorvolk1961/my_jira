"""Репозиторий чата."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.system import ChatMessage


def list_messages(db: Session, limit: int = 200) -> list[dict[str, object]]:
    rows = (
        db.execute(
            text(
                "SELECT c.*, u.login FROM chat_message c"
                " LEFT JOIN app_user u ON c.user_id = u.id"
                " ORDER BY c.id DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in reversed(rows)]


def create(db: Session, user_id: int, author: str, text: str) -> None:
    db.add(ChatMessage(user_id=user_id, author=author, text=text))
    db.commit()
