"""Репозиторий задач: запросы и CRUD (только SQL/ORM)."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models.work import Task

_LIST_SQL = text(
    """
    SELECT t.id, t.description, t.deadline, t.requirement_id, t.stage_id, t.status_id, t.priority_id,
           r.description AS req_desc, p.name AS project_name, p.id AS project_id,
           pst.name AS stage_name, tt.name AS type_name,
           pr.name AS priority_name, ts.name AS status_name, ts.color AS status_color
    FROM task t
    LEFT JOIN requirement r ON t.requirement_id = r.id
    LEFT JOIN project_stage ps ON t.stage_id = ps.id
    LEFT JOIN project_stage_type pst ON ps.stage_type_id = pst.id
    LEFT JOIN project p ON p.id = COALESCE(ps.project_id, r.project_id)
    LEFT JOIN task_type tt ON t.task_type_id = tt.id
    JOIN priority pr ON t.priority_id = pr.id
    JOIN task_status ts ON t.status_id = ts.id
    WHERE t.is_deleted=0
    ORDER BY t.id DESC
    """
)

_DETAIL_SQL = text(
    """
    SELECT t.id, t.description, t.deadline, t.status_id, t.priority_id, t.requirement_id,
           t.stage_id, t.task_type_id,
           pr.name AS prio, ts.name AS st, ts.color AS color,
           p.name AS pname, COALESCE(ps.project_id, r.project_id) AS pid,
           pst.name AS stype, r.description AS req_desc, tt.name AS type_name
    FROM task t
    JOIN priority pr ON t.priority_id = pr.id
    JOIN task_status ts ON t.status_id = ts.id
    LEFT JOIN project_stage ps ON t.stage_id = ps.id
    LEFT JOIN project_stage_type pst ON ps.stage_type_id = pst.id
    LEFT JOIN requirement r ON t.requirement_id = r.id
    LEFT JOIN task_type tt ON t.task_type_id = tt.id
    LEFT JOIN project p ON p.id = COALESCE(ps.project_id, r.project_id)
    WHERE t.id=:id AND t.is_deleted=0
    """
)

_SUBTASKS_SQL = text(
    """
    SELECT s.id, s.description, s.deadline, s.status_id, s.priority_id,
           pr.name AS prio, ts.name AS st, ts.color AS color
    FROM subtask s
    JOIN priority pr ON s.priority_id = pr.id
    JOIN task_status ts ON s.status_id = ts.id
    WHERE s.parent_task_id=:id AND s.is_deleted=0
    ORDER BY s.id
    """
)


def list_tasks(db: Session) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(_LIST_SQL).mappings().all()]


def get(db: Session, task_id: int) -> Task | None:
    return db.execute(select(Task).where(Task.id == task_id, Task.is_deleted == 0)).scalars().first()


def get_row(db: Session, task_id: int) -> dict[str, Any] | None:
    row = db.execute(_DETAIL_SQL, {"id": task_id}).mappings().first()
    return dict(row) if row else None


def subtasks_of(db: Session, task_id: int) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(_SUBTASKS_SQL, {"id": task_id}).mappings().all()]


def create(
    db: Session,
    *,
    requirement_id: int,
    description: str,
    stage_id: int,
    task_type_id: int,
    priority_id: int,
    deadline: date | None,
    status_id: int,
) -> Task:
    task = Task(
        requirement_id=requirement_id,
        description=description,
        stage_id=stage_id,
        task_type_id=task_type_id,
        priority_id=priority_id,
        deadline=deadline,
        status_id=status_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update(
    db: Session,
    task: Task,
    *,
    requirement_id: int,
    description: str,
    stage_id: int,
    task_type_id: int,
    priority_id: int,
    deadline: date | None,
    status_id: int,
) -> None:
    task.requirement_id = requirement_id
    task.description = description
    task.stage_id = stage_id
    task.task_type_id = task_type_id
    task.priority_id = priority_id
    task.deadline = deadline
    task.status_id = status_id
    task.updated_at = datetime.now()
    db.commit()


def set_status(db: Session, task: Task, status_id: int) -> None:
    task.status_id = status_id
    task.updated_at = datetime.now()
    db.commit()


def soft_delete(db: Session, task: Task) -> None:
    task.is_deleted = 1
    task.updated_at = datetime.now()
    db.commit()


def soft_delete_cascade(db: Session, task: Task) -> None:
    """Мягко удаляет задачу и её прямые подзадачи одним коммитом (как legacy task_delete)."""
    db.execute(
        text(
            "UPDATE subtask SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE parent_task_id=:tid AND is_deleted=0"
        ),
        {"tid": task.id},
    )
    task.is_deleted = 1
    task.updated_at = datetime.now()
    db.commit()


def comments(db: Session, entity_type: str, entity_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            "SELECT * FROM comment WHERE entity_type=:etype AND entity_id=:eid AND is_deleted=0"
            " ORDER BY created_at DESC, id DESC"
        ),
        {"etype": entity_type, "eid": entity_id},
    ).mappings()
    return [dict(row) for row in rows.all()]


def status_list(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(text("SELECT id, name FROM task_status WHERE is_deleted=0 ORDER BY id")).mappings()
    return [dict(row) for row in rows.all()]


def priority_options(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(text("SELECT id, name FROM priority WHERE is_deleted=0 ORDER BY id")).mappings()
    return [dict(row) for row in rows.all()]


def task_type_options(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(text("SELECT id, name FROM task_type WHERE is_deleted=0 ORDER BY id")).mappings()
    return [dict(row) for row in rows.all()]


def requirement_options(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            "SELECT r.id, r.description, p.name AS project_name FROM requirement r"
            " JOIN project p ON r.project_id=p.id WHERE r.is_deleted=0 ORDER BY r.id"
        )
    ).mappings()
    return [dict(row) for row in rows.all()]


def stage_options(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            "SELECT ps.id, ps.project_id, p.name AS project_name, pst.name AS type_name"
            " FROM project_stage ps JOIN project p ON ps.project_id=p.id"
            " JOIN project_stage_type pst ON ps.stage_type_id=pst.id"
            " WHERE ps.is_deleted=0 ORDER BY ps.id"
        )
    ).mappings()
    return [dict(row) for row in rows.all()]


def task_options(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(text("SELECT id, description FROM task WHERE is_deleted=0 ORDER BY id")).mappings()
    return [dict(row) for row in rows.all()]


def employee_options(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        text("SELECT id, last_name, first_name FROM employee WHERE is_deleted=0 ORDER BY last_name")
    ).mappings()
    return [dict(row) for row in rows.all()]
