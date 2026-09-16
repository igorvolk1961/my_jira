"""Проекты: бизнес-логика (навигация, CRUD, вкладки карточки)."""

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import project_repo

Row = dict[str, Any]


def list_projects(db: Session) -> list[dict[str, object]]:
    return project_repo.list_active(db)


def set_current(db: Session, project_id: int) -> bool:
    return project_repo.get(db, project_id) is not None


def list_for_table(db: Session) -> list[Row]:
    return project_repo.list_with_refs(db)


def get_detail(db: Session, project_id: int) -> Row | None:
    return project_repo.get_detail(db, project_id)


def form_options(db: Session) -> dict[str, list[Row]]:
    return project_repo.form_options(db)


def _to_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _to_date(value: Any) -> date | None:
    text = str(value).strip() if value else ""
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _to_float(value: Any) -> float | None:
    text = str(value).strip() if value else ""
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _build_values(form: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    name = str(form.get("name") or "").strip()
    priority_id = _to_int(form.get("priority_id"))
    if not name:
        return {}, "Укажите название проекта"
    if not priority_id:
        return {}, "Укажите приоритет проекта"
    cost_raw = form.get("cost")
    if cost_raw not in (None, "") and _to_float(cost_raw) is None:
        return {}, "Стоимость должна быть числом"
    values: dict[str, Any] = {
        "name": name,
        "description": str(form.get("description") or "").strip() or None,
        "main_stakeholder_id": _to_int(form.get("main_stakeholder_id")) or None,
        "cost": _to_float(cost_raw),
        "mvp_deadline": _to_date(form.get("mvp_deadline")),
        "deadline": _to_date(form.get("deadline")),
        "priority_id": priority_id,
    }
    return values, ""


def create(db: Session, form: Mapping[str, Any]) -> str:
    values, error = _build_values(form)
    if error:
        return error
    project_repo.create(db, values)
    return ""


def update(db: Session, project_id: int, form: Mapping[str, Any]) -> str:
    item = project_repo.get(db, project_id)
    if item is None:
        return "Проект не найден"
    values, error = _build_values(form)
    if error:
        return error
    project_repo.update(db, item, values)
    return ""


def delete(db: Session, project_id: int) -> None:
    project_repo.soft_delete(db, project_id)


def stakeholder_data(db: Session, project_id: int) -> dict[str, Any]:
    return project_repo.stakeholder_data(db, project_id)


def add_stakeholder(db: Session, project_id: int, stakeholder_id: int) -> bool:
    return project_repo.add_stakeholder(db, project_id, stakeholder_id)


def remove_stakeholder(db: Session, project_id: int, stakeholder_id: int) -> None:
    project_repo.remove_stakeholder(db, project_id, stakeholder_id)


def employee_data(db: Session, project_id: int) -> dict[str, Any]:
    rows = project_repo.list_employees(db, project_id)
    return {"rows": rows, "candidates": project_repo.list_employee_candidates(db, project_id)}


def add_employee(db: Session, project_id: int, employee_id: int) -> bool:
    return project_repo.add_employee(db, project_id, employee_id)


def remove_employee(db: Session, project_id: int, employee_id: int) -> None:
    project_repo.remove_employee(db, project_id, employee_id)
