"""Требования: бизнес-логика."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import requirement_repo

Row = dict[str, Any]


def _to_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def list_requirements(db: Session) -> list[Row]:
    return requirement_repo.list_all(db)


def for_project(db: Session, project_id: int) -> list[Row]:
    return requirement_repo.list_for_project(db, project_id)


def detail(db: Session, requirement_id: int) -> tuple[Row | None, list[Row]]:
    requirement = requirement_repo.get_detail(db, requirement_id)
    if requirement is None:
        return None, []
    return requirement, requirement_repo.list_tasks(db, requirement_id)


def form_options(db: Session) -> dict[str, list[Row]]:
    return requirement_repo.form_options(db)


def _build_values(form: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    project_id = _to_int(form.get("project_id"))
    requirement_type_id = _to_int(form.get("requirement_type_id"))
    priority_id = _to_int(form.get("priority_id"))
    description = str(form.get("description") or "").strip()
    if not project_id or not requirement_type_id or not priority_id or not description:
        return {}, "Заполните обязательные поля требования"
    values: dict[str, Any] = {
        "project_id": project_id,
        "stakeholder_id": _to_int(form.get("stakeholder_id")) or None,
        "requirement_type_id": requirement_type_id,
        "nfr_type_id": _to_int(form.get("nfr_type_id")) or None,
        "description": description,
        "priority_id": priority_id,
        "acceptance_criteria": str(form.get("acceptance_criteria") or "").strip() or None,
    }
    return values, ""


def create(db: Session, form: Mapping[str, Any]) -> tuple[int, str]:
    values, error = _build_values(form)
    if error:
        return 0, error
    item = requirement_repo.create(db, values)
    task_id = _to_int(form.get("task_id"))
    if task_id:
        requirement_repo.link_task(db, task_id, item.id)
    return item.id, ""


def update(db: Session, requirement_id: int, form: Mapping[str, Any]) -> str:
    item = requirement_repo.get(db, requirement_id)
    if item is None:
        return "Требование не найдено"
    values, error = _build_values(form)
    if error:
        return error
    requirement_repo.update(db, item, values)
    return ""


def delete(db: Session, requirement_id: int) -> None:
    requirement_repo.soft_delete(db, requirement_id)
