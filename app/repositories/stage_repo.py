"""Репозиторий этапов проектов (SQL/ORM)."""

from typing import Any

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.db.models.projects import ProjectStage

Row = dict[str, Any]


def list_all(db: Session) -> list[Row]:
    rows = (
        db.execute(
            text(
                "SELECT ps.*, p.name as project_name, pst.name as type_name, pss.name as status_name, pss.color"
                " FROM project_stage ps"
                " JOIN project p ON ps.project_id = p.id"
                " JOIN project_stage_type pst ON ps.stage_type_id = pst.id"
                " JOIN project_stage_status pss ON ps.status_id = pss.id"
                " WHERE ps.is_deleted=0"
                " ORDER BY p.name, pst.sort_order"
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get_detail(db: Session, stage_id: int) -> Row | None:
    row = (
        db.execute(
            text(
                "SELECT ps.*, p.name pname, pst.name type_name, pss.name status_name, pss.color"
                " FROM project_stage ps"
                " JOIN project p ON ps.project_id=p.id"
                " JOIN project_stage_type pst ON ps.stage_type_id=pst.id"
                " JOIN project_stage_status pss ON ps.status_id=pss.id"
                " WHERE ps.id=:sid AND ps.is_deleted=0"
            ),
            {"sid": stage_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_tasks(db: Session, stage_id: int) -> list[Row]:
    rows = (
        db.execute(
            text(
                "SELECT t.id, t.description, t.deadline, pr.name prio, ts.name st, ts.color color,"
                " (SELECT GROUP_CONCAT(e.last_name || ' ' || e.first_name, ', ')"
                "  FROM task_assignment ta JOIN employee e ON ta.employee_id=e.id"
                "  WHERE ta.task_id=t.id AND ta.task_kind='task' AND ta.is_deleted=0) executors"
                " FROM task t"
                " JOIN priority pr ON t.priority_id=pr.id"
                " JOIN task_status ts ON t.status_id=ts.id"
                " WHERE t.stage_id=:sid AND t.is_deleted=0"
                " ORDER BY t.id"
            ),
            {"sid": stage_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get(db: Session, stage_id: int) -> ProjectStage | None:
    return (
        db.execute(select(ProjectStage).where(ProjectStage.id == stage_id, ProjectStage.is_deleted == 0))
        .scalars()
        .first()
    )


def create(db: Session, values: dict[str, Any]) -> ProjectStage:
    item = ProjectStage(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update(db: Session, item: ProjectStage, values: dict[str, Any]) -> None:
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()


def soft_delete(db: Session, stage_id: int) -> None:
    """Мягкое удаление этапа вместе с его задачами и подзадачами (как в legacy)."""
    task_ids = [
        int(row[0])
        for row in db.execute(
            text("SELECT id FROM task WHERE stage_id=:sid AND is_deleted=0"), {"sid": stage_id}
        ).fetchall()
    ]
    if task_ids:
        db.execute(
            text(
                "UPDATE subtask SET is_deleted=1, updated_at=CURRENT_TIMESTAMP"
                " WHERE parent_task_id IN :ids AND is_deleted=0"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": task_ids},
        )
        db.execute(
            text("UPDATE task SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            ),
            {"ids": task_ids},
        )
    db.execute(
        text("UPDATE project_stage SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:sid"),
        {"sid": stage_id},
    )
    db.commit()


def form_options(db: Session) -> dict[str, list[Row]]:
    projects = [
        dict(r)
        for r in db.execute(text("SELECT id, name FROM project WHERE is_deleted=0 ORDER BY id")).mappings().all()
    ]
    stage_types = [
        dict(r)
        for r in db.execute(text("SELECT id, name FROM project_stage_type WHERE is_deleted=0 ORDER BY sort_order"))
        .mappings()
        .all()
    ]
    stage_statuses = [
        dict(r)
        for r in db.execute(text("SELECT id, name FROM project_stage_status WHERE is_deleted=0 ORDER BY id"))
        .mappings()
        .all()
    ]
    return {"projects": projects, "stage_types": stage_types, "stage_statuses": stage_statuses}


def _assignments(db: Session, kind: str, ids: list[int]) -> list[Row]:
    if not ids:
        return []
    rows = (
        db.execute(
            text(
                "SELECT ta.*, e.id as eid, e.last_name, e.first_name,"
                " COALESCE(TRIM(au.last_name || ' ' || au.first_name), ap.login, '—') as assigner"
                " FROM task_assignment ta"
                " JOIN employee e ON ta.employee_id = e.id"
                " LEFT JOIN app_user ap ON ta.assigned_by_user_id = ap.id"
                " LEFT JOIN employee au ON ap.employee_id = au.id"
                " WHERE ta.is_deleted=0 AND ta.task_kind=:kind AND ta.task_id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"kind": kind, "ids": ids},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def tree_rows(db: Session, project_id: int) -> dict[str, list[Row]]:
    """Сырые строки для дерева этапы → задачи → подзадачи проекта."""
    stages = [
        dict(r)
        for r in db.execute(
            text(
                "SELECT ps.*, pst.name as type_name, pss.name as status_name, pss.color"
                " FROM project_stage ps"
                " JOIN project_stage_type pst ON ps.stage_type_id = pst.id"
                " JOIN project_stage_status pss ON ps.status_id = pss.id"
                " WHERE ps.project_id=:pid AND ps.is_deleted=0"
                " ORDER BY pst.sort_order"
            ),
            {"pid": project_id},
        )
        .mappings()
        .all()
    ]
    tasks = [
        dict(r)
        for r in db.execute(
            text(
                "SELECT t.*, ps.id as stage_id, pr.name as priority_name,"
                " ts.name as status_name, ts.color as status_color, tt.name as type_name"
                " FROM task t"
                " JOIN priority pr ON t.priority_id = pr.id"
                " JOIN task_status ts ON t.status_id = ts.id"
                " LEFT JOIN project_stage ps ON t.stage_id = ps.id"
                " LEFT JOIN requirement r ON t.requirement_id = r.id"
                " LEFT JOIN task_type tt ON t.task_type_id = tt.id"
                " WHERE t.is_deleted=0 AND (ps.project_id=:pid OR r.project_id=:pid)"
                " ORDER BY t.id"
            ),
            {"pid": project_id},
        )
        .mappings()
        .all()
    ]
    task_ids = [int(t["id"]) for t in tasks]
    subtasks: list[Row] = []
    if task_ids:
        subtasks = [
            dict(r)
            for r in db.execute(
                text(
                    "SELECT st.*, pr.name as priority_name, ts.name as status_name, ts.color as status_color"
                    " FROM subtask st"
                    " JOIN priority pr ON st.priority_id = pr.id"
                    " JOIN task_status ts ON st.status_id = ts.id"
                    " WHERE st.is_deleted=0 AND st.parent_task_id IN :ids"
                    " ORDER BY st.id"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": task_ids},
            )
            .mappings()
            .all()
        ]
    subtask_ids = [int(s["id"]) for s in subtasks]
    assignments = _assignments(db, "task", task_ids) + _assignments(db, "subtask", subtask_ids)
    return {"stages": stages, "tasks": tasks, "subtasks": subtasks, "assignments": assignments}
