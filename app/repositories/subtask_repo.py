"""Репозиторий подзадач: запросы, CRUD и обход дерева (только SQL/ORM)."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models.work import Subtask

_LIST_SQL = text(
    """
    SELECT st.id, st.description, st.deadline, st.parent_task_id, st.parent_subtask_id,
           st.status_id, st.priority_id, st.stage_id,
           t.description AS parent_desc, pr.name AS priority_name,
           ts.name AS status_name, ts.color AS status_color
    FROM subtask st
    JOIN task t ON st.parent_task_id = t.id
    JOIN priority pr ON st.priority_id = pr.id
    JOIN task_status ts ON st.status_id = ts.id
    WHERE st.is_deleted=0
    ORDER BY st.id DESC
    """
)

_DETAIL_SQL = text(
    """
    SELECT s.id, s.parent_task_id, s.parent_subtask_id, s.description, s.deadline,
           s.status_id, s.priority_id, s.stage_id,
           t.description AS parent_desc, t.id AS parent_id,
           pr.name AS prio, ts.name AS st, ts.color AS color
    FROM subtask s
    JOIN task t ON s.parent_task_id = t.id
    JOIN priority pr ON s.priority_id = pr.id
    JOIN task_status ts ON s.status_id = ts.id
    WHERE s.id=:id AND s.is_deleted=0
    """
)


def list_subtasks(db: Session) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(_LIST_SQL).mappings().all()]


def get(db: Session, subtask_id: int) -> Subtask | None:
    return db.execute(select(Subtask).where(Subtask.id == subtask_id, Subtask.is_deleted == 0)).scalars().first()


def get_row(db: Session, subtask_id: int) -> dict[str, Any] | None:
    row = db.execute(_DETAIL_SQL, {"id": subtask_id}).mappings().first()
    return dict(row) if row else None


def list_active(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(text("SELECT id, description FROM subtask WHERE is_deleted=0 ORDER BY id")).mappings()
    return [dict(row) for row in rows.all()]


def parent_map(db: Session) -> dict[int, tuple[int | None, int | None]]:
    rows = db.execute(text("SELECT id, parent_task_id, parent_subtask_id FROM subtask WHERE is_deleted=0")).mappings()
    return {row["id"]: (row["parent_task_id"], row["parent_subtask_id"]) for row in rows.all()}


def ancestors(db: Session, subtask_id: int) -> list[tuple[str, int]]:
    """Предки подзадачи: (родительская задача, цепочка родительских подзадач)."""
    res: list[tuple[str, int]] = []
    cur = (
        db.execute(
            text("SELECT parent_task_id, parent_subtask_id FROM subtask WHERE id=:id AND is_deleted=0"),
            {"id": subtask_id},
        )
        .mappings()
        .first()
    )
    if not cur:
        return res
    res.append(("task", int(cur["parent_task_id"])))
    parent = cur["parent_subtask_id"]
    while parent:
        res.append(("subtask", int(parent)))
        pc = (
            db.execute(text("SELECT parent_subtask_id FROM subtask WHERE id=:id AND is_deleted=0"), {"id": parent})
            .mappings()
            .first()
        )
        parent = pc["parent_subtask_id"] if pc else None
    return res


def soft_delete_tree(db: Session, root_id: int) -> None:
    """Мягко удаляет подзадачу и всё её поддерево (без commit)."""
    ids = [
        row[0]
        for row in db.execute(text("SELECT id FROM subtask WHERE id=:id AND is_deleted=0"), {"id": root_id}).all()
    ]
    frontier = list(ids)
    while frontier:
        placeholders = ",".join(f":p{i}" for i in range(len(frontier)))
        params = {f"p{i}": value for i, value in enumerate(frontier)}
        kids = db.execute(
            text(f"SELECT id FROM subtask WHERE parent_subtask_id IN ({placeholders}) AND is_deleted=0"),
            params,
        ).all()
        frontier = [row[0] for row in kids]
        ids.extend(frontier)
    if ids:
        placeholders = ",".join(f":p{i}" for i in range(len(ids)))
        params = {f"p{i}": value for i, value in enumerate(ids)}
        db.execute(
            text(f"UPDATE subtask SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})"),
            params,
        )
    db.commit()


def create(
    db: Session,
    *,
    parent_task_id: int,
    parent_subtask_id: int | None,
    description: str,
    stage_id: int | None,
    priority_id: int,
    deadline: date | None,
    status_id: int,
) -> Subtask:
    subtask = Subtask(
        parent_task_id=parent_task_id,
        parent_subtask_id=parent_subtask_id,
        description=description,
        stage_id=stage_id,
        priority_id=priority_id,
        deadline=deadline,
        status_id=status_id,
    )
    db.add(subtask)
    db.commit()
    db.refresh(subtask)
    return subtask


def update(
    db: Session,
    subtask: Subtask,
    *,
    parent_task_id: int,
    description: str,
    stage_id: int | None,
    priority_id: int,
    deadline: date | None,
    status_id: int,
) -> None:
    subtask.parent_task_id = parent_task_id
    subtask.description = description
    subtask.stage_id = stage_id
    subtask.priority_id = priority_id
    subtask.deadline = deadline
    subtask.status_id = status_id
    subtask.updated_at = datetime.now()
    db.commit()


def set_status(db: Session, subtask: Subtask, status_id: int) -> None:
    subtask.status_id = status_id
    subtask.updated_at = datetime.now()
    db.commit()
