"""View-модель прав пользователя для шаблонов."""

from typing import Any

User = dict[str, Any] | None


def is_admin(user: User) -> bool:
    return bool(user and user.get("role") == "admin")


def is_analyst(user: User) -> bool:
    return bool(user and user.get("is_analyst"))


def can_edit_artifacts(user: User) -> bool:
    """Документные артефакты и требования правят администратор и системный аналитик."""
    return is_admin(user) or is_analyst(user)
