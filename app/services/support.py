"""Небольшие общие помощники сервисного слоя (без SQL и HTTP)."""

from datetime import date
from typing import Any

User = dict[str, Any] | None


def is_admin_user(user: User) -> bool:
    return bool(user and user.get("role") == "admin")


def to_int(value: Any) -> int | None:
    text = str(value).strip() if value is not None else ""
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def to_float(value: Any) -> float | None:
    text = str(value).strip() if value is not None else ""
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_date(value: Any) -> date | None:
    text = str(value).strip() if value is not None else ""
    if text == "":
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None
