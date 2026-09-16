"""Репозиторий персональных списков задач («Мои задачи» и админ-вкладки)."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.repositories.assignment_repo import assigner_sql

_ASSIGNER = assigner_sql("e2", "u2")

_TASK_TMPL = """
    SELECT 'task' AS kind, t.id AS id, t.description AS description,
           COALESCE(ps.project_id, r.project_id) AS project_id, p.name AS project_name,
           pr.name AS priority_name, t.deadline AS deadline,
           ts.id AS status_id, ts.name AS status_name, ts.color AS status_color,
           (SELECT GROUP_CONCAT(TRIM(e3.last_name || ' ' || e3.first_name), ', ')
              FROM task_assignment ta3 JOIN employee e3 ON ta3.employee_id = e3.id
             WHERE ta3.task_id = t.id AND ta3.task_kind = 'task' AND ta3.is_deleted = 0) AS executors,
           (SELECT {assigner}
              FROM task_assignment ta2 LEFT JOIN app_user u2 ON ta2.assigned_by_user_id = u2.id
              LEFT JOIN employee e2 ON u2.employee_id = e2.id
             WHERE ta2.task_id = t.id AND ta2.task_kind = 'task' AND ta2.is_deleted = 0
             ORDER BY ta2.assigned_at DESC, ta2.id DESC LIMIT 1) AS assigner
    FROM task t
    JOIN priority pr ON t.priority_id = pr.id
    JOIN task_status ts ON t.status_id = ts.id
    LEFT JOIN project_stage ps ON t.stage_id = ps.id
    LEFT JOIN requirement r ON t.requirement_id = r.id
    LEFT JOIN project p ON p.id = COALESCE(ps.project_id, r.project_id)
    WHERE t.is_deleted = 0 {extra}
"""

_SUBTASK_TMPL = """
    SELECT 'subtask' AS kind, s.id AS id, s.description AS description,
           COALESCE(ps.project_id, r.project_id) AS project_id, p.name AS project_name,
           pr.name AS priority_name, s.deadline AS deadline,
           ts.id AS status_id, ts.name AS status_name, ts.color AS status_color,
           (SELECT GROUP_CONCAT(TRIM(e3.last_name || ' ' || e3.first_name), ', ')
              FROM task_assignment ta3 JOIN employee e3 ON ta3.employee_id = e3.id
             WHERE ta3.task_id = s.id AND ta3.task_kind = 'subtask' AND ta3.is_deleted = 0) AS executors,
           (SELECT {assigner}
              FROM task_assignment ta2 LEFT JOIN app_user u2 ON ta2.assigned_by_user_id = u2.id
              LEFT JOIN employee e2 ON u2.employee_id = e2.id
             WHERE ta2.task_id = s.id AND ta2.task_kind = 'subtask' AND ta2.is_deleted = 0
             ORDER BY ta2.assigned_at DESC, ta2.id DESC LIMIT 1) AS assigner
    FROM subtask s
    JOIN task t ON s.parent_task_id = t.id
    JOIN priority pr ON s.priority_id = pr.id
    JOIN task_status ts ON s.status_id = ts.id
    LEFT JOIN project_stage ps ON t.stage_id = ps.id
    LEFT JOIN requirement r ON t.requirement_id = r.id
    LEFT JOIN project p ON p.id = COALESCE(ps.project_id, r.project_id)
    WHERE s.is_deleted = 0 {extra}
"""

_DONE_STATUSES = "('Выполнена', 'Отменена')"
_ACCEPTED_STATUSES = "('Принята к исполнению', 'Выполнена', 'Отменена')"


def _task_sql(extra: str = "") -> str:
    return _TASK_TMPL.format(assigner=_ASSIGNER, extra=extra)


def _subtask_sql(extra: str = "") -> str:
    return _SUBTASK_TMPL.format(assigner=_ASSIGNER, extra=extra)


def _tab_extra(alias: str, tab: str, kind: str) -> str:
    kind_literal = f"'{kind}'"
    if tab == "unassigned":
        return (
            f"AND NOT EXISTS (SELECT 1 FROM task_assignment ta "
            f"WHERE ta.task_id={alias}.id AND ta.task_kind={kind_literal} AND ta.is_deleted=0)"
        )
    if tab == "not_accepted":
        return (
            f"AND EXISTS (SELECT 1 FROM task_assignment ta "
            f"WHERE ta.task_id={alias}.id AND ta.task_kind={kind_literal} AND ta.is_deleted=0) "
            f"AND {alias}.status_id NOT IN (SELECT id FROM task_status WHERE name IN {_ACCEPTED_STATUSES})"
        )
    return (
        f"AND {alias}.deadline IS NOT NULL AND {alias}.deadline < date('now') "
        f"AND {alias}.status_id NOT IN (SELECT id FROM task_status WHERE name IN {_DONE_STATUSES})"
    )


def my_items(db: Session, employee_id: int, managed_ids: set[int]) -> list[dict[str, Any]]:
    """Задачи/подзадачи сотрудника, отфильтрованные в SQL (не тянем всю таблицу)."""
    items: list[dict[str, Any]] = []
    task_extra = (
        "AND EXISTS (SELECT 1 FROM task_assignment ta WHERE ta.task_id=t.id"
        " AND ta.task_kind='task' AND ta.employee_id=:eid AND ta.is_deleted=0)"
    )
    items.extend(dict(row) for row in db.execute(text(_task_sql(task_extra)), {"eid": employee_id}).mappings().all())

    managed = sorted(managed_ids)
    orphan = ""
    params: dict[str, Any] = {"eid": employee_id}
    if managed:
        placeholders = ",".join(f":m{i}" for i in range(len(managed)))
        params.update({f"m{i}": value for i, value in enumerate(managed)})
        orphan = (
            f" OR (s.id IN ({placeholders}) AND NOT EXISTS (SELECT 1 FROM task_assignment ta"
            " WHERE ta.task_id=s.id AND ta.task_kind='subtask' AND ta.is_deleted=0))"
        )
    sub_extra = (
        "AND (EXISTS (SELECT 1 FROM task_assignment ta WHERE ta.task_id=s.id"
        " AND ta.task_kind='subtask' AND ta.employee_id=:eid AND ta.is_deleted=0)"
        f"{orphan})"
    )
    items.extend(dict(row) for row in db.execute(text(_subtask_sql(sub_extra)), params).mappings().all())
    return items


def items_for_tab(db: Session, tab: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for kind, builder, alias in (("task", _task_sql, "t"), ("subtask", _subtask_sql, "s")):
        extra = _tab_extra(alias, tab, kind)
        items.extend(dict(row) for row in db.execute(text(builder(extra))).mappings().all())
    return items
