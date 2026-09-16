"""Репозиторий событий."""

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_active(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.execute(text("SELECT * FROM event WHERE is_deleted=0 ORDER BY occurred_at DESC, id DESC")).mappings().all()
    )
    return [dict(row) for row in rows]


def get(db: Session, event_id: int) -> dict[str, Any] | None:
    row = db.execute(text("SELECT * FROM event WHERE id=:id AND is_deleted=0"), {"id": event_id}).mappings().first()
    return dict(row) if row else None


def create(db: Session, description: str, decision: str | None, occurred_at: datetime) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO event (occurred_at, description, decision)
            VALUES (:occurred_at, :description, :decision)
            RETURNING id
            """
        ),
        {"occurred_at": occurred_at, "description": description, "decision": decision},
    )
    return int(result.scalar_one())


def update(db: Session, event_id: int, description: str, decision: str | None, occurred_at: datetime | None) -> None:
    db.execute(
        text(
            """
            UPDATE event SET occurred_at=:occurred_at, description=:description, decision=:decision,
                   updated_at=CURRENT_TIMESTAMP
            WHERE id=:id
            """
        ),
        {"occurred_at": occurred_at, "description": description, "decision": decision, "id": event_id},
    )


def soft_delete(db: Session, event_id: int) -> None:
    db.execute(
        text("UPDATE event SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
        {"id": event_id},
    )
