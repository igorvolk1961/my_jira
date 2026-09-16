"""События: бизнес-логика."""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import event_repo


def list_events(db: Session) -> list[dict[str, Any]]:
    return event_repo.list_active(db)


def get_event(db: Session, event_id: int) -> dict[str, Any] | None:
    return event_repo.get(db, event_id)


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def create_event(db: Session, form: dict[str, Any]) -> tuple[str, int | None]:
    description = str(form.get("description") or "").strip()
    if not description:
        return "Укажите описание события", None
    decision = str(form.get("decision")).strip() if form.get("decision") else None
    occurred_at = _parse_datetime(form.get("occurred_at")) or datetime.now()
    event_id = event_repo.create(db, description, decision, occurred_at)
    db.commit()
    return "", event_id


def update_event(db: Session, event_id: int, form: dict[str, Any]) -> str:
    description = str(form.get("description") or "").strip()
    if not description:
        return "Укажите описание события"
    decision = str(form.get("decision")).strip() if form.get("decision") else None
    occurred_at = _parse_datetime(form.get("occurred_at"))
    event_repo.update(db, event_id, description, decision, occurred_at)
    db.commit()
    return ""


def delete_event(db: Session, event_id: int) -> None:
    event_repo.soft_delete(db, event_id)
    db.commit()
