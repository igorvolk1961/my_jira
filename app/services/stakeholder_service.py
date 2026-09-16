"""Стейкхолдеры: бизнес-логика."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories import employee_repo, stakeholder_repo

MIDDLE_NAME = "middle_name"


def list_stakeholders(db: Session) -> list[dict[str, Any]]:
    return stakeholder_repo.list_active(db)


def get_stakeholder(db: Session, stakeholder_id: int) -> dict[str, Any] | None:
    return stakeholder_repo.get(db, stakeholder_id)


def stakeholder_detail(db: Session, stakeholder_id: int) -> dict[str, Any] | None:
    stakeholder = stakeholder_repo.get_detail(db, stakeholder_id)
    if not stakeholder:
        return None
    return {
        "stakeholder": stakeholder,
        "projects": stakeholder_repo.detail_projects(db, stakeholder_id),
        "requirements": stakeholder_repo.detail_requirements(db, stakeholder_id),
        "interviews": stakeholder_repo.detail_interviews(db, stakeholder_id),
    }


def form_options(db: Session, stakeholder_id: int | None = None) -> dict[str, Any]:
    linked = stakeholder_repo.linked_employee_ids(db)
    employees = [e for e in stakeholder_repo.available_employees(db) if int(e["id"]) not in linked]
    if stakeholder_id:
        stakeholder = stakeholder_repo.get(db, stakeholder_id)
        current_id = stakeholder.get("employee_id") if stakeholder else None
        if current_id and all(int(e["id"]) != int(current_id) for e in employees):
            current = stakeholder_repo.employee_by_id(db, int(current_id))
            if current:
                employees.append(current)
    return {
        "types": stakeholder_repo.list_types(db),
        "priorities": stakeholder_repo.list_priorities(db),
        "employees": employees,
        "dev_id": employee_repo.developer_type_id(db),
    }


def _int_field(form: dict[str, Any], name: str, default: int | None = None) -> int | None:
    raw = form.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw))
    except ValueError:
        return None


def _build_values(db: Session, form: dict[str, Any]) -> tuple[dict[str, Any], str]:
    last_name = str(form.get("last_name") or "").strip()
    first_name = str(form.get("first_name") or "").strip()
    if not last_name or not first_name:
        return {}, "Поля «Фамилия» и «Имя» обязательны"
    type_id = _int_field(form, "type_id")
    if type_id is None:
        return {}, "Некорректный тип стейкхолдера"
    priority = _int_field(form, "priority")
    if priority is None:
        return {}, "Некорректный приоритет"
    employee_id = None
    if type_id == employee_repo.developer_type_id(db):
        employee_id = _int_field(form, "employee_id")
    values = {
        "last_name": last_name,
        "first_name": first_name,
        "middle_name": (str(form.get(MIDDLE_NAME)).strip() if form.get(MIDDLE_NAME) else None),
        "type_id": type_id,
        "position": (str(form.get("position")).strip() if form.get("position") else None),
        "priority": priority,
        "employee_id": employee_id,
    }
    return values, ""


def create_stakeholder(db: Session, form: dict[str, Any]) -> tuple[str, int | None]:
    values, error = _build_values(db, form)
    if error:
        return error, None
    stakeholder_id = stakeholder_repo.create(db, values)
    project_id = _int_field(form, "project_id")
    if project_id:
        stakeholder_repo.add_project_stakeholder(db, project_id, stakeholder_id)
    if values["employee_id"]:
        employee_repo.set_employee_stackholder(db, int(values["employee_id"]))
    db.commit()
    return "", stakeholder_id


def update_stakeholder(db: Session, stakeholder_id: int, form: dict[str, Any]) -> str:
    values, error = _build_values(db, form)
    if error:
        return error
    old = stakeholder_repo.get(db, stakeholder_id)
    old_employee_id = old.get("employee_id") if old else None
    stakeholder_repo.update(db, stakeholder_id, values)
    if values["employee_id"]:
        employee_repo.set_employee_stackholder(db, int(values["employee_id"]))
    if old_employee_id and str(old_employee_id) != str(values["employee_id"] or ""):
        employee_repo.reset_employee_stackholder_if_unlinked(db, int(old_employee_id))
    db.commit()
    return ""


def delete_stakeholder(db: Session, stakeholder_id: int) -> None:
    stakeholder = stakeholder_repo.get(db, stakeholder_id)
    stakeholder_repo.soft_delete(db, stakeholder_id)
    if stakeholder and stakeholder.get("employee_id"):
        employee_repo.reset_employee_stackholder_if_unlinked(db, int(stakeholder["employee_id"]))
    db.commit()
