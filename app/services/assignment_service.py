"""Назначения задач: загрузка сотрудников, создание/правка с проверками."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories import assignment_repo, employee_repo, subtask_repo
from app.services import settings_service, subtask_service
from app.services.support import User, is_admin_user, to_float, to_int

MAX_LOAD = 1.0


def list_assignments(db: Session) -> list[dict[str, Any]]:
    return assignment_repo.list_assignments(db)


def get_row(db: Session, assignment_id: int) -> dict[str, Any] | None:
    return assignment_repo.get_row(db, assignment_id)


def covered_for_employee(db: Session, employee_id: int) -> set[tuple[str, int]]:
    """Позиции (kind, id), где занятость в предке покрыта подзадачей."""
    return employee_repo.covered_for_employee(db, employee_id)


def projected_load_after(
    db: Session,
    employee_id: int,
    kind: str,
    task_id: int,
    new_share: float,
    exclude_assignment_id: int = 0,
) -> float:
    """Загрузка после добавления назначения; предки подзадачи исключаются."""
    ancestors = set(subtask_repo.ancestors(db, task_id)) if kind == "subtask" else set()
    rows = assignment_repo.rows_for_employee(db, employee_id, exclude_assignment_id)
    covered = covered_for_employee(db, employee_id)
    total = sum(
        float(r["share"])
        for r in rows
        if (r["task_kind"], r["task_id"]) not in ancestors and (r["task_kind"], r["task_id"]) not in covered
    )
    return total + new_share


def _load_error(load: float) -> str:
    return f"Суммарная загрузка сотрудника не может превышать 100% ({round(load * 100)}%)"


def create(db: Session, form: dict[str, Any], user: User) -> tuple[str, str]:
    """Создаёт назначение. Возвращает (ошибка, сообщение)."""
    admin_mode = is_admin_user(user)
    task_id = to_int(form.get("task_id"))
    kind = str(form.get("task_kind") or "")
    if task_id is None:
        return "Выберите задачу", ""
    employee_raw = str(form.get("employee_id") or "").strip()

    if not employee_raw:
        if admin_mode:
            return "Выберите исполнителя", ""
        employee_id = user.get("employee_id") if user else None
        if kind != "subtask" or not employee_id or not subtask_service.can_manage(db, employee_id, task_id):
            return "Недостаточно прав для снятия исполнителя", ""
        existing = assignment_repo.active_subtask_assignment(db, task_id)
        if existing is not None:
            assignment_repo.soft_delete(db, existing)
        return "", "Исполнитель подзадачи снят"

    employee_id = to_int(employee_raw)
    if employee_id is None:
        return "Выберите исполнителя", ""

    if not admin_mode:
        owner_id = user.get("employee_id") if user else None
        if kind != "subtask":
            return "Пользователь может назначать исполнителей только на подзадачи", ""
        if not owner_id or not subtask_service.can_manage(db, owner_id, task_id):
            return "Недостаточно прав для назначения на эту подзадачу", ""
        if not settings_service.allow_users_assign_subtask_executors(db) and employee_id != owner_id:
            return "Настройка запрещает назначать других исполнителей подзадач", ""

    project_id = assignment_repo.project_id_for(db, kind, task_id)
    if project_id is not None and not assignment_repo.is_project_member(db, project_id, employee_id):
        return "Исполнитель не назначен на проект задачи", ""

    new_share = to_float(form.get("share"))
    if new_share is None:
        return "Некорректная доля", ""

    existing = assignment_repo.active_subtask_assignment(db, task_id) if kind == "subtask" else None
    exclude_id = existing.id if existing is not None else 0
    load = projected_load_after(db, employee_id, kind, task_id, new_share, exclude_id)
    if load > MAX_LOAD + 1e-9:
        return _load_error(load), ""

    if kind == "subtask" and existing is not None:
        assignment_repo.replace_executor(
            db,
            existing,
            employee_id=employee_id,
            share=new_share,
            assigned_by_user_id=user.get("id") if user else None,
        )
        return "", "Исполнитель подзадачи заменён (у подзадачи один исполнитель)"

    assignment_repo.create(
        db,
        task_id=task_id,
        task_kind=kind,
        employee_id=employee_id,
        share=new_share,
        assigned_by_user_id=user.get("id") if user else None,
    )
    return "", "Назначение создано"


def update(db: Session, assignment_id: int, form: dict[str, Any], user: User) -> str:
    task_id = to_int(form.get("task_id"))
    kind = str(form.get("task_kind") or "")
    employee_id = to_int(form.get("employee_id"))
    if task_id is None or employee_id is None:
        return "Заполните обязательные поля назначения"

    project_id = assignment_repo.project_id_for(db, kind, task_id)
    if project_id is not None and not assignment_repo.is_project_member(db, project_id, employee_id):
        return "Исполнитель не назначен на проект задачи"

    if kind == "subtask" and assignment_repo.conflict_subtask_assignment(db, task_id, assignment_id):
        return "У подзадачи уже есть исполнитель (только один)"

    new_share = to_float(form.get("share"))
    if new_share is None:
        return "Некорректная доля"
    load = projected_load_after(db, employee_id, kind, task_id, new_share, assignment_id)
    if load > MAX_LOAD + 1e-9:
        return _load_error(load)

    assignment = assignment_repo.get(db, assignment_id)
    if assignment is None:
        return "Назначение не найдено"
    assignment_repo.update(
        db,
        assignment,
        task_id=task_id,
        task_kind=kind,
        employee_id=employee_id,
        share=new_share,
        assigned_by_user_id=user.get("id") if user else None,
    )
    return ""


def delete(db: Session, assignment_id: int) -> bool:
    assignment = assignment_repo.get(db, assignment_id)
    if assignment is None:
        return False
    assignment_repo.soft_delete(db, assignment)
    return True
