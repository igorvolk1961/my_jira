"""Настройки приложения."""

from sqlalchemy.orm import Session

from app.repositories import settings_repo

ALLOW_USERS_ASSIGN_SUBTASK_EXECUTORS = "allow_users_assign_subtask_executors"


def get_setting(db: Session, key: str, default: str | None = None) -> str | None:
    return settings_repo.get(db, key, default)


def set_setting(db: Session, key: str, value: str) -> None:
    settings_repo.set_value(db, key, value)


def allow_users_assign_subtask_executors(db: Session) -> bool:
    return get_setting(db, ALLOW_USERS_ASSIGN_SUBTASK_EXECUTORS, "1") == "1"
