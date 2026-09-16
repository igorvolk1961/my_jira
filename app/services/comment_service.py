"""Комментарии: бизнес-логика."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories import comment_repo

ENTITY_TYPES = ("task", "subtask")


def entity_label(db: Session, entity_type: str, entity_id: int) -> str | None:
    return comment_repo.entity_label(db, entity_type, entity_id)


def create_comment(db: Session, user: dict[str, Any], form: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    entity_type = str(form.get("entity_type") or "").strip()
    if entity_type not in ENTITY_TYPES:
        return "Некорректный тип сущности", {}
    raw_id = str(form.get("entity_id") or "").strip()
    try:
        entity_id = int(raw_id)
    except ValueError:
        return "Некорректный идентификатор сущности", {}
    text_value = str(form.get("text") or "").strip()
    if not text_value:
        return "Текст комментария обязателен", {}
    comment_repo.create(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        author=str(user.get("full_name") or "") or None,
        user_id=int(user["id"]),
        text_value=text_value,
    )
    db.commit()
    return "", {"entity_type": entity_type, "entity_id": entity_id}


def delete_comment(db: Session, user: dict[str, Any], comment_id: int) -> tuple[str, dict[str, Any] | None]:
    comment = comment_repo.get(db, comment_id)
    if not comment:
        return "Комментарий не найден", None
    is_admin = user.get("role") == "admin"
    if not is_admin and comment.get("user_id") != user.get("id"):
        return "Можно удалять только свои комментарии", comment
    comment_repo.soft_delete(db, comment_id)
    db.commit()
    return "", comment
