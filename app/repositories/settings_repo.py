"""Репозиторий настроек (ключ-значение)."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def get(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.execute(text("SELECT value FROM setting WHERE key=:key"), {"key": key}).first()
    return row[0] if row else default


def set_value(db: Session, key: str, value: str) -> None:
    db.execute(
        text(
            "INSERT INTO setting (key, value, updated_at) VALUES (:key, :value, CURRENT_TIMESTAMP)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP"
        ),
        {"key": key, "value": value},
    )
    db.commit()
