"""Репозиторий назначений: SQL по task_assignment (только SQL/ORM)."""

from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models.work import TaskAssignment


def assigner_sql(employee_alias: str, user_alias: str, extra_fallback: str | None = None) -> str:
    """SQL-выражение «ФИО того, кто назначил» с единым набором fallback-ов."""
    parts = [f"TRIM({employee_alias}.last_name || ' ' || {employee_alias}.first_name)"]
    if extra_fallback:
        parts.append(extra_fallback)
    parts.append(f"{user_alias}.login")
    parts.append("'—'")
    return "COALESCE(" + ", ".join(parts) + ")"


_LIST_SQL = text(
    """
    SELECT ta.id, ta.task_id, ta.task_kind, ta.employee_id, ta.share, ta.assigned_by_user_id,
           ta.assigned_at, e.last_name, e.first_name,
           CASE WHEN ta.task_kind='task' THEN (SELECT description FROM task WHERE id=ta.task_id)
                ELSE (SELECT description FROM subtask WHERE id=ta.task_id) END AS task_desc
    FROM task_assignment ta
    JOIN employee e ON ta.employee_id = e.id
    WHERE ta.is_deleted=0
    ORDER BY ta.id DESC
    """
)

_DETAIL_SQL = text(
    """
    SELECT ta.id, ta.task_id, ta.task_kind, ta.employee_id, ta.share,
           e.last_name, e.first_name, pt.name AS pos,
           CASE WHEN ta.task_kind='task' THEN (SELECT description FROM task WHERE id=ta.task_id)
                ELSE (SELECT description FROM subtask WHERE id=ta.task_id) END AS task_desc
    FROM task_assignment ta
    JOIN employee e ON ta.employee_id = e.id
    LEFT JOIN position_type pt ON e.position_type_id = pt.id
    WHERE ta.id=:id AND ta.is_deleted=0
    """
)


def list_assignments(db: Session) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(_LIST_SQL).mappings().all()]


def get(db: Session, assignment_id: int) -> TaskAssignment | None:
    return (
        db.execute(select(TaskAssignment).where(TaskAssignment.id == assignment_id, TaskAssignment.is_deleted == 0))
        .scalars()
        .first()
    )


def get_row(db: Session, assignment_id: int) -> dict[str, Any] | None:
    row = db.execute(_DETAIL_SQL, {"id": assignment_id}).mappings().first()
    return dict(row) if row else None


def rows_for_employee(db: Session, employee_id: int, exclude_id: int = 0) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            "SELECT task_id, task_kind, share FROM task_assignment"
            " WHERE employee_id=:eid AND is_deleted=0 AND id<>:exclude"
        ),
        {"eid": employee_id, "exclude": exclude_id},
    ).mappings()
    return [dict(row) for row in rows.all()]


def active_subtask_assignment(db: Session, subtask_id: int) -> TaskAssignment | None:
    return (
        db.execute(
            select(TaskAssignment)
            .where(
                TaskAssignment.task_id == subtask_id,
                TaskAssignment.task_kind == "subtask",
                TaskAssignment.is_deleted == 0,
            )
            .limit(1)
        )
        .scalars()
        .first()
    )


def subtask_assignee(db: Session, subtask_id: int) -> int | None:
    row = db.execute(
        text(
            "SELECT employee_id FROM task_assignment WHERE task_id=:id AND task_kind='subtask' AND is_deleted=0 LIMIT 1"
        ),
        {"id": subtask_id},
    ).first()
    return int(row[0]) if row else None


def active_task_assignee(db: Session, task_id: int, employee_id: int) -> bool:
    row = db.execute(
        text(
            "SELECT 1 FROM task_assignment"
            " WHERE task_id=:tid AND task_kind='task' AND employee_id=:eid AND is_deleted=0 LIMIT 1"
        ),
        {"tid": task_id, "eid": employee_id},
    ).first()
    return row is not None


def is_project_member(db: Session, project_id: int, employee_id: int) -> bool:
    row = db.execute(
        text("SELECT COUNT(*) FROM project_employee WHERE project_id=:pid AND employee_id=:eid AND is_deleted=0"),
        {"pid": project_id, "eid": employee_id},
    ).first()
    return bool(row and row[0])


def project_id_for(db: Session, kind: str, task_id: int) -> int | None:
    if kind == "task":
        row = db.execute(
            text(
                "SELECT COALESCE(ps.project_id, r.project_id) FROM task t"
                " LEFT JOIN project_stage ps ON t.stage_id=ps.id"
                " LEFT JOIN requirement r ON t.requirement_id=r.id"
                " WHERE t.id=:id AND t.is_deleted=0"
            ),
            {"id": task_id},
        ).first()
    else:
        row = db.execute(
            text(
                "SELECT COALESCE(ps.project_id, r.project_id) FROM subtask s"
                " JOIN task t ON s.parent_task_id=t.id"
                " LEFT JOIN project_stage ps ON t.stage_id=ps.id"
                " LEFT JOIN requirement r ON t.requirement_id=r.id"
                " WHERE s.id=:id AND s.is_deleted=0"
            ),
            {"id": task_id},
        ).first()
    return int(row[0]) if row and row[0] is not None else None


def create(
    db: Session,
    *,
    task_id: int,
    task_kind: str,
    employee_id: int,
    share: float,
    assigned_by_user_id: int | None,
) -> TaskAssignment:
    assignment = TaskAssignment(
        task_id=task_id,
        task_kind=task_kind,
        employee_id=employee_id,
        share=share,
        assigned_by_user_id=assigned_by_user_id,
        assigned_at=datetime.now(),
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def replace_executor(
    db: Session,
    assignment: TaskAssignment,
    *,
    employee_id: int,
    share: float,
    assigned_by_user_id: int | None,
) -> None:
    assignment.employee_id = employee_id
    assignment.share = share
    assignment.assigned_by_user_id = assigned_by_user_id
    assignment.assigned_at = datetime.now()
    assignment.updated_at = datetime.now()
    db.commit()


def update(
    db: Session,
    assignment: TaskAssignment,
    *,
    task_id: int,
    task_kind: str,
    employee_id: int,
    share: float,
    assigned_by_user_id: int | None,
) -> None:
    assignment.task_id = task_id
    assignment.task_kind = task_kind
    assignment.employee_id = employee_id
    assignment.share = share
    assignment.assigned_by_user_id = assigned_by_user_id
    assignment.assigned_at = datetime.now()
    assignment.updated_at = datetime.now()
    db.commit()


def soft_delete(db: Session, assignment: TaskAssignment) -> None:
    assignment.is_deleted = 1
    assignment.updated_at = datetime.now()
    db.commit()


def conflict_subtask_assignment(db: Session, subtask_id: int, exclude_id: int) -> bool:
    row = db.execute(
        text(
            "SELECT id FROM task_assignment"
            " WHERE task_id=:id AND task_kind='subtask' AND is_deleted=0 AND id<>:exclude LIMIT 1"
        ),
        {"id": subtask_id, "exclude": exclude_id},
    ).first()
    return row is not None


def project_employee_options(db: Session) -> dict[int, list[dict[str, Any]]]:
    """Сотрудники по проектам с должностью и текущей загруженностью (сумма долей)."""
    result: dict[int, list[dict[str, Any]]] = {}
    rows = db.execute(
        text(
            """
            SELECT pe.project_id, e.id, e.last_name, e.first_name, pt.name AS pos,
                   COALESCE((SELECT SUM(ta.share) FROM task_assignment ta
                             WHERE ta.employee_id=e.id AND ta.is_deleted=0), 0) AS load
            FROM project_employee pe
            JOIN employee e ON pe.employee_id=e.id
            JOIN position_type pt ON e.position_type_id=pt.id
            WHERE pe.is_deleted=0 AND e.is_deleted=0
            ORDER BY e.last_name
            """
        )
    ).mappings()
    for row in rows.all():
        result.setdefault(int(row["project_id"]), []).append(dict(row))
    return result


def executors_for(db: Session, kind: str, entity_id: int) -> list[dict[str, Any]]:
    assigner = assigner_sql("au", "ap")
    rows = db.execute(
        text(
            f"""
            SELECT e.id AS eid, e.last_name, e.first_name, pt.name AS pos, ta.share,
                   {assigner} AS assigner, ta.assigned_at AS assigned_at
            FROM task_assignment ta
            JOIN employee e ON ta.employee_id=e.id
            LEFT JOIN position_type pt ON e.position_type_id=pt.id
            LEFT JOIN app_user ap ON ta.assigned_by_user_id=ap.id
            LEFT JOIN employee au ON ap.employee_id=au.id
            WHERE ta.task_id=:id AND ta.task_kind=:kind AND ta.is_deleted=0
            ORDER BY ta.id
            """
        ),
        {"id": entity_id, "kind": kind},
    ).mappings()
    return [dict(row) for row in rows.all()]
