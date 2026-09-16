"""Чат: чтение и отправка сообщений."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories import chat_repo

MAX_TEXT = 4000


def list_messages(db: Session) -> list[dict[str, object]]:
    return chat_repo.list_messages(db)


def post_message(db: Session, user: dict[str, Any], raw_text: str) -> str:
    """Создаёт сообщение. Возвращает текст ошибки или пустую строку."""
    text = (raw_text or "").strip()
    if not text:
        return "Сообщение не может быть пустым"
    chat_repo.create(db, int(user["id"]), str(user["full_name"]), text[:MAX_TEXT])
    return ""
