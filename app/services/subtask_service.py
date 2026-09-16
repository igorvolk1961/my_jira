"""Подзадачи: бизнес-логика, права управления и обход дерева."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.repositories import assignment_repo, subtask_repo, task_repo
from app.services.support import User, is_admin_user, to_date, to_int


def list_subtasks(db: Session) -> list[dict[str, Any]]:
    return subtask_repo.list_subtasks(db)


def list_active(db: Session) -> list[dict[str, Any]]:
    return subtask_repo.list_active(db)


def get_row(db: Session, subtask_id: int) -> dict[str, Any] | None:
    return subtask_repo.get_row(db, subtask_id)


def can_manage(db: Session, employee_id: int | None, subtask_id: int) -> bool:
    """Исполнитель подзадачи (или ближайшего предка) может ей управлять."""
    if not employee_id:
        return False
    target = assignment_repo.subtask_assignee(db, subtask_id)
    if target is not None:
        return target == employee_id
    cur = subtask_repo.get(db, subtask_id)
    if cur is None:
        return False
    parent_task_id, parent_subtask_id = cur.parent_task_id, cur.parent_subtask_id
    while True:
        if parent_subtask_id:
            assignee = assignment_repo.subtask_assignee(db, parent_subtask_id)
            if assignee is not None:
                return assignee == employee_id
            parent = subtask_repo.get(db, parent_subtask_id)
            if parent is None:
                return False
            parent_task_id, parent_subtask_id = parent.parent_task_id, parent.parent_subtask_id
        else:
            return assignment_repo.active_task_assignee(db, parent_task_id, employee_id) if parent_task_id else False


def managed_ids(db: Session, employee_id: int | None) -> set[int]:
    """Множество подзадач, которыми управляет сотрудник, без N+1."""
    if not employee_id:
        return set()
    task_asg = {
        row["task_id"]: row["employee_id"]
        for row in db.execute(
            text("SELECT task_id, employee_id FROM task_assignment WHERE task_kind='task' AND is_deleted=0")
        ).mappings()
    }
    sub_asg = {
        row["task_id"]: row["employee_id"]
        for row in db.execute(
            text("SELECT task_id, employee_id FROM task_assignment WHERE task_kind='subtask' AND is_deleted=0")
        ).mappings()
    }
    parents = subtask_repo.parent_map(db)

    def can(subtask_id: int) -> bool:
        target = sub_asg.get(subtask_id)
        if target is not None:
            return target == employee_id
        cur = parents.get(subtask_id)
        if not cur:
            return False
        parent_task_id, parent_subtask_id = cur
        while True:
            if parent_subtask_id is not None:
                assignee = sub_asg.get(parent_subtask_id)
                if assignee is not None:
                    return assignee == employee_id
                nxt = parents.get(parent_subtask_id)
                if not nxt:
                    return False
                parent_task_id, parent_subtask_id = nxt
            else:
                return task_asg.get(parent_task_id) == employee_id if parent_task_id else False

    return {subtask_id for subtask_id in parents if can(subtask_id)}


def resolve_parent(db: Session, parent_task_id_raw: Any, parent_subtask_id_raw: Any) -> tuple[int | None, int | None]:
    """Определяет (parent_task_id, parent_subtask_id) по данным формы (как legacy)."""
    parent_subtask_id = to_int(parent_subtask_id_raw)
    parent_task_id = to_int(parent_task_id_raw)
    if parent_subtask_id:
        root = subtask_repo.get(db, parent_subtask_id)
        if root is not None:
            parent_task_id = root.parent_task_id
        else:
            parent_subtask_id = None
    return parent_task_id, parent_subtask_id


def create(db: Session, form: dict[str, Any], user: User) -> tuple[str, int | None]:
    """Создаёт подзадачу. Возвращает (ошибка, id)."""
    parent_task_id, parent_subtask_id = resolve_parent(db, form.get("parent_task_id"), form.get("parent_subtask_id"))
    if not parent_task_id:
        return "Подзадача должна относиться к задаче", None

    if not is_admin_user(user):
        employee_id = user.get("employee_id") if user else None
        if employee_id is None:
            allowed = False
        elif parent_subtask_id:
            allowed = can_manage(db, employee_id, parent_subtask_id)
        else:
            allowed = assignment_repo.active_task_assignee(db, parent_task_id, employee_id)
        if not allowed:
            return "Недостаточно прав: можно создавать подзадачи только в своих задачах", None

    description = str(form.get("description") or "").strip()
    priority_id = to_int(form.get("priority_id"))
    status_id = to_int(form.get("status_id"))
    if not description or priority_id is None or status_id is None:
        return "Заполните обязательные поля подзадачи", None

    subtask = subtask_repo.create(
        db,
        parent_task_id=parent_task_id,
        parent_subtask_id=parent_subtask_id,
        description=description,
        stage_id=to_int(form.get("stage_id")),
        priority_id=priority_id,
        deadline=to_date(form.get("deadline")),
        status_id=status_id,
    )
    return "", subtask.id


def update(db: Session, subtask_id: int, form: dict[str, Any], user: User) -> str:
    if not is_admin_user(user) and not can_manage(db, user.get("employee_id") if user else None, subtask_id):
        return "Недостаточно прав для изменения этой подзадачи"
    subtask = subtask_repo.get(db, subtask_id)
    if subtask is None:
        return "Подзадача не найдена"
    parent_task_id = to_int(form.get("parent_task_id"))
    description = str(form.get("description") or "").strip()
    priority_id = to_int(form.get("priority_id"))
    status_id = to_int(form.get("status_id"))
    if not parent_task_id or not description or priority_id is None or status_id is None:
        return "Заполните обязательные поля подзадачи"
    subtask_repo.update(
        db,
        subtask,
        parent_task_id=parent_task_id,
        description=description,
        stage_id=to_int(form.get("stage_id")),
        priority_id=priority_id,
        deadline=to_date(form.get("deadline")),
        status_id=status_id,
    )
    return ""


def delete(db: Session, subtask_id: int, user: User) -> str:
    if not is_admin_user(user) and not can_manage(db, user.get("employee_id") if user else None, subtask_id):
        return "Недостаточно прав для удаления этой подзадачи"
    subtask_repo.soft_delete_tree(db, subtask_id)
    return ""


def detail(db: Session, subtask_id: int, user: User) -> dict[str, Any] | None:
    row = subtask_repo.get_row(db, subtask_id)
    if row is None:
        return None
    employee_id = user.get("employee_id") if user else None
    can_status = is_admin_user(user) or can_manage(db, employee_id, subtask_id)
    children = _children(db, subtask_id)
    return {
        "subtask": row,
        "executors": assignment_repo.executors_for(db, "subtask", subtask_id),
        "statuses": task_repo.status_list(db),
        "comments": task_repo.comments(db, "subtask", subtask_id),
        "children": children,
        "project_id": assignment_repo.project_id_for(db, "subtask", subtask_id),
        "can_status": can_status,
    }


def _children(db: Session, subtask_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text("SELECT id, description FROM subtask WHERE parent_subtask_id=:id AND is_deleted=0 ORDER BY id"),
        {"id": subtask_id},
    ).mappings()
    return [dict(row) for row in rows.all()]


def change_status(db: Session, subtask_id: int, status_id: int | None, user: User) -> tuple[bool, bool]:
    """Возвращает (разрешено, изменено)."""
    employee_id = user.get("employee_id") if user else None
    allowed = is_admin_user(user) or can_manage(db, employee_id, subtask_id)
    if not allowed or status_id is None:
        return allowed, False
    subtask = subtask_repo.get(db, subtask_id)
    if subtask is None:
        return True, False
    subtask_repo.set_status(db, subtask, status_id)
    return True, True
