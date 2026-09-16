"""Сотрудники: бизнес-логика."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories import employee_repo

MIDDLE_NAME = "middle_name"


def list_employees(db: Session) -> list[dict[str, Any]]:
    return employee_repo.list_active(db)


def get_employee(db: Session, employee_id: int) -> dict[str, Any] | None:
    return employee_repo.get(db, employee_id)


def form_options(db: Session) -> dict[str, Any]:
    return {
        "positions": employee_repo.list_positions(db),
        "statuses": employee_repo.list_statuses(db),
    }


def employee_detail(db: Session, employee_id: int) -> dict[str, Any] | None:
    employee = employee_repo.get_detail(db, employee_id)
    if not employee:
        return None
    covered = employee_repo.covered_for_employee(db, employee_id)
    tasks = [row for row in employee_repo.assigned_tasks(db, employee_id) if ("task", int(row["id"])) not in covered]
    subtasks = [
        row for row in employee_repo.assigned_subtasks(db, employee_id) if ("subtask", int(row["id"])) not in covered
    ]
    return {
        "employee": employee,
        "load": employee_repo.effective_load(db, employee_id),
        "tasks": tasks,
        "subtasks": subtasks,
    }


def _int_field(form: dict[str, Any], name: str, default: int | None = None) -> int | None:
    raw = form.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw))
    except ValueError:
        return None


def _build_values(form: dict[str, Any]) -> tuple[dict[str, Any], str]:
    last_name = str(form.get("last_name") or "").strip()
    first_name = str(form.get("first_name") or "").strip()
    if not last_name or not first_name:
        return {}, "Поля «Фамилия» и «Имя» обязательны"
    position_id = _int_field(form, "position_type_id")
    if position_id is None:
        return {}, "Некорректный тип должности"
    status_id = _int_field(form, "status_id")
    if status_id is None:
        return {}, "Некорректный статус"
    values = {
        "last_name": last_name,
        "first_name": first_name,
        "middle_name": (str(form.get(MIDDLE_NAME)).strip() if form.get(MIDDLE_NAME) else None),
        "position_type_id": position_id,
        "status_id": status_id,
        "subordinates_total": _int_field(form, "subordinates_total", 0) or 0,
        "subordinates_available": _int_field(form, "subordinates_available", 0) or 0,
        "is_stackholder": 1 if form.get("is_stackholder") else 0,
    }
    return values, ""


def create_employee(db: Session, form: dict[str, Any]) -> tuple[str, int | None]:
    values, error = _build_values(form)
    if error:
        return error, None
    employee_id = employee_repo.create(db, values)
    project_id = _int_field(form, "project_id")
    if project_id:
        employee_repo.add_project_employee(db, project_id, employee_id)
    employee_repo.sync_stakeholder_for_employee(db, employee_id, bool(values["is_stackholder"]))
    employee_repo.sync_analyst_role_from_position(db, employee_id)
    db.commit()
    return "", employee_id


def update_employee(db: Session, employee_id: int, form: dict[str, Any]) -> str:
    values, error = _build_values(form)
    if error:
        return error
    employee_repo.update(db, employee_id, values)
    employee_repo.sync_stakeholder_for_employee(db, employee_id, bool(values["is_stackholder"]))
    employee_repo.sync_analyst_role_from_position(db, employee_id)
    db.commit()
    return ""


def delete_employee(db: Session, employee_id: int, me: dict[str, Any] | None) -> tuple[str, str]:
    """Возвращает (ошибка, сообщение об успехе)."""
    if me and me.get("employee_id") == employee_id:
        return "Нельзя удалить собственную учётную запись", ""
    linked = employee_repo.deactivate_users_for_employee(db, employee_id)
    employee_repo.soft_delete_employee(db, employee_id)
    db.commit()
    message = "Сотрудник и связанный пользователь удалены" if linked else "Сотрудник удалён"
    return "", message


def change_role(db: Session, employee_id: int, form: dict[str, Any], me: dict[str, Any] | None) -> str:
    role = str(form.get("role") or "")
    want_analyst = 1 if form.get("is_analyst") else 0
    if role not in ("admin", "user"):
        return "Некорректная роль"
    user = employee_repo.get_active_user_for_employee(db, employee_id)
    if not user:
        return "У сотрудника нет учётной записи пользователя"
    if me and me.get("employee_id") == employee_id:
        return "Нельзя изменить собственную роль"
    employee_repo.set_user_role(db, int(user["id"]), role, want_analyst)
    employee_repo.sync_position_from_analyst_role(db, employee_id, bool(want_analyst))
    db.commit()
    return ""
