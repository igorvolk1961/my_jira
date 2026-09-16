"""Персональные списки: «Мои задачи» и админ-вкладки задач."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories import assignment_repo, personal_repo
from app.services import subtask_service
from app.services.support import User

VALID_TABS = ("unassigned", "not_accepted", "overdue")


def my_tasks(db: Session, user: User) -> list[dict[str, Any]]:
    employee_id = user.get("employee_id") if user else None
    if not employee_id:
        return []
    managed = subtask_service.managed_ids(db, employee_id)
    return personal_repo.my_items(db, employee_id, managed)


def normalize_tab(tab: str | None) -> str:
    return tab if tab in VALID_TABS else "unassigned"


def admin_tasks(db: Session, tab: str | None) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    normalized = normalize_tab(tab)
    items = personal_repo.items_for_tab(db, normalized)
    return items, assignment_repo.project_employee_options(db)
