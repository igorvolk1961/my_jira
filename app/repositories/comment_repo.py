"""Репозиторий комментариев."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def get(db: Session, comment_id: int) -> dict[str, Any] | None:
    row = db.execute(text("SELECT * FROM comment WHERE id=:id AND is_deleted=0"), {"id": comment_id}).mappings().first()
    return dict(row) if row else None


def create(db: Session, entity_type: str, entity_id: int, author: str | None, user_id: int, text_value: str) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO comment (entity_type, entity_id, author, user_id, text)
            VALUES (:etype, :eid, :author, :user_id, :text)
            RETURNING id
            """
        ),
        {
            "etype": entity_type,
            "eid": entity_id,
            "author": author,
            "user_id": user_id,
            "text": text_value,
        },
    )
    return int(result.scalar_one())


def soft_delete(db: Session, comment_id: int) -> None:
    db.execute(
        text("UPDATE comment SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
        {"id": comment_id},
    )


def entity_label(db: Session, entity_type: str, entity_id: int) -> str | None:
    if entity_type == "task":
        row = db.execute(text("SELECT description FROM task WHERE id=:id AND is_deleted=0"), {"id": entity_id}).first()
    else:
        row = db.execute(
            text("SELECT description FROM subtask WHERE id=:id AND is_deleted=0"), {"id": entity_id}
        ).first()
    return str(row[0]) if row else None
