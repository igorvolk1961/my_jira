"""Задачи: бизнес-логика, детальная страница и смена статуса."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories import assignment_repo, task_repo
from app.services.support import User, is_admin_user, to_date, to_int


def list_tasks(db: Session) -> list[dict[str, Any]]:
    return task_repo.list_tasks(db)


def get_row(db: Session, task_id: int) -> dict[str, Any] | None:
    return task_repo.get_row(db, task_id)


def status_list(db: Session) -> list[dict[str, Any]]:
    return task_repo.status_list(db)


def requirement_options(db: Session) -> list[dict[str, Any]]:
    return task_repo.requirement_options(db)


def stage_options(db: Session) -> list[dict[str, Any]]:
    return task_repo.stage_options(db)


def priority_options(db: Session) -> list[dict[str, Any]]:
    return task_repo.priority_options(db)


def task_type_options(db: Session) -> list[dict[str, Any]]:
    return task_repo.task_type_options(db)


def task_options(db: Session) -> list[dict[str, Any]]:
    return task_repo.task_options(db)


def employee_options(db: Session) -> list[dict[str, Any]]:
    return task_repo.employee_options(db)


def detail(db: Session, task_id: int, user: User) -> dict[str, Any] | None:
    row = task_repo.get_row(db, task_id)
    if row is None:
        return None
    employee_id = user.get("employee_id") if user else None
    can_status = is_admin_user(user) or bool(
        employee_id and assignment_repo.active_task_assignee(db, task_id, employee_id)
    )
    return {
        "task": row,
        "executors": assignment_repo.executors_for(db, "task", task_id),
        "statuses": task_repo.status_list(db),
        "subtasks": task_repo.subtasks_of(db, task_id),
        "comments": task_repo.comments(db, "task", task_id),
        "can_status": can_status,
    }


def create(db: Session, form: dict[str, Any]) -> tuple[str, int | None]:
    """Создаёт задачу. Возвращает (ошибка, id)."""
    stage_id = to_int(form.get("stage_id"))
    if stage_id is None:
        return "Задача должна быть создана под этапом — выберите этап", None
    requirement_id = to_int(form.get("requirement_id"))
    if requirement_id is None:
        return "Задача должна относиться к требованию — выберите требование", None
    task_type_id = to_int(form.get("task_type_id"))
    if task_type_id is None:
        return "Выберите тип задачи", None
    description = str(form.get("description") or "").strip()
    priority_id = to_int(form.get("priority_id"))
    status_id = to_int(form.get("status_id"))
    if not description or priority_id is None or status_id is None:
        return "Заполните обязательные поля задачи", None
    task = task_repo.create(
        db,
        requirement_id=requirement_id,
        description=description,
        stage_id=stage_id,
        task_type_id=task_type_id,
        priority_id=priority_id,
        deadline=to_date(form.get("deadline")),
        status_id=status_id,
    )
    return "", task.id


def update(db: Session, task_id: int, form: dict[str, Any]) -> str:
    task = task_repo.get(db, task_id)
    if task is None:
        return "Задача не найдена"
    stage_id = to_int(form.get("stage_id"))
    if stage_id is None:
        return "Задача должна быть под этапом — выберите этап"
    requirement_id = to_int(form.get("requirement_id"))
    if requirement_id is None:
        return "Задача должна относиться к требованию — выберите требование"
    task_type_id = to_int(form.get("task_type_id"))
    if task_type_id is None:
        return "Выберите тип задачи"
    description = str(form.get("description") or "").strip()
    priority_id = to_int(form.get("priority_id"))
    status_id = to_int(form.get("status_id"))
    if not description or priority_id is None or status_id is None:
        return "Заполните обязательные поля задачи"
    task_repo.update(
        db,
        task,
        requirement_id=requirement_id,
        description=description,
        stage_id=stage_id,
        task_type_id=task_type_id,
        priority_id=priority_id,
        deadline=to_date(form.get("deadline")),
        status_id=status_id,
    )
    return ""


def delete(db: Session, task_id: int) -> bool:
    task = task_repo.get(db, task_id)
    if task is None:
        return False
    task_repo.soft_delete_cascade(db, task)
    return True


def change_status(db: Session, task_id: int, status_id: int | None, user: User) -> tuple[bool, bool]:
    """Возвращает (разрешено, изменено)."""
    employee_id = user.get("employee_id") if user else None
    allowed = is_admin_user(user) or bool(
        employee_id and assignment_repo.active_task_assignee(db, task_id, employee_id)
    )
    if not allowed or status_id is None:
        return allowed, False
    task = task_repo.get(db, task_id)
    if task is None:
        return True, False
    task_repo.set_status(db, task, status_id)
    return True, True
