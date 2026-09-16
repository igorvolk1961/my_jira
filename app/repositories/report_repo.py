"""Репозиторий отчётов: SQL-выборки (порт legacy routes_reports.py)."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

Row = dict[str, Any]


def _rows(db: Session, sql: str, params: dict[str, Any] | None = None) -> list[Row]:
    return [dict(row) for row in db.execute(text(sql), params or {}).mappings().all()]


def _scalar(db: Session, sql: str, params: dict[str, Any] | None = None) -> Any:
    return db.execute(text(sql), params or {}).scalar()


# ==================== Проекты ====================


def project_stats(db: Session) -> Row:
    return {
        "total": int(_scalar(db, "SELECT COUNT(*) FROM project WHERE is_deleted=0") or 0),
        "cost": float(_scalar(db, "SELECT COALESCE(SUM(cost), 0) FROM project WHERE is_deleted=0") or 0),
        "budget": int(_scalar(db, "SELECT COUNT(*) FROM project WHERE is_deleted=0 AND cost IS NOT NULL") or 0),
    }


def projects_by_priority(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT pr.name, pr.weight, COUNT(p.id) cnt, COALESCE(SUM(p.cost), 0) cost
        FROM priority pr
        LEFT JOIN project p ON p.priority_id=pr.id AND p.is_deleted=0
        WHERE pr.is_deleted=0
        GROUP BY pr.id ORDER BY pr.weight
        """,
    )


def project_progress(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT p.id, p.name,
            (SELECT COUNT(*) FROM project_stage ps WHERE ps.project_id=p.id AND ps.is_deleted=0) stages,
            (SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
                WHERE ps.project_id=p.id AND ps.is_deleted=0 AND pss.name='Завершён') stages_done,
            (SELECT COUNT(*) FROM task t
                LEFT JOIN project_stage ps ON t.stage_id=ps.id
                LEFT JOIN requirement r ON t.requirement_id=r.id
                WHERE t.is_deleted=0 AND COALESCE(ps.project_id, r.project_id)=p.id) tasks,
            (SELECT COUNT(*) FROM task t
                LEFT JOIN project_stage ps ON t.stage_id=ps.id
                LEFT JOIN requirement r ON t.requirement_id=r.id
                JOIN task_status ts ON t.status_id=ts.id
                WHERE t.is_deleted=0 AND COALESCE(ps.project_id, r.project_id)=p.id
                  AND ts.name='Выполнена') tasks_done
        FROM project p WHERE p.is_deleted=0 ORDER BY p.name
        """,
    )


# ==================== Стейкхолдеры ====================


def stakeholder_total(db: Session) -> int:
    return int(_scalar(db, "SELECT COUNT(*) FROM stakeholder WHERE is_deleted=0") or 0)


def stakeholder_types(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT st.name, st.influence_priority inf, st.interest_priority ints, COUNT(s.id) cnt
        FROM stakeholder_type st
        LEFT JOIN stakeholder s ON s.type_id=st.id AND s.is_deleted=0
        WHERE st.is_deleted=0
        GROUP BY st.id ORDER BY st.influence_priority DESC, st.interest_priority DESC
        """,
    )


# ==================== Сотрудники ====================


def employee_stats(db: Session) -> Row:
    return {
        "total": int(_scalar(db, "SELECT COUNT(*) FROM employee WHERE is_deleted=0") or 0),
        "available": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM employee e JOIN employee_status es ON e.status_id=es.id
                WHERE e.is_deleted=0 AND es.is_available=1
                """,
            )
            or 0
        ),
        "assigned": int(_scalar(db, "SELECT COUNT(DISTINCT employee_id) FROM task_assignment WHERE is_deleted=0") or 0),
    }


def employee_load(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT e.id, e.last_name, e.first_name, pt.name pos, es.name st, es.is_available av,
               (SELECT COUNT(*) FROM task_assignment ta WHERE ta.employee_id=e.id AND ta.is_deleted=0) acnt,
               COALESCE((SELECT SUM(ta.share) FROM task_assignment ta
                         WHERE ta.employee_id=e.id AND ta.is_deleted=0), 0) lshare
        FROM employee e
        JOIN position_type pt ON e.position_type_id=pt.id
        JOIN employee_status es ON e.status_id=es.id
        WHERE e.is_deleted=0
        ORDER BY lshare DESC
        """,
    )


def employees_by_position(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT pt.name, COUNT(e.id) cnt,
               COALESCE(SUM(CASE WHEN es.is_available=1 THEN 1 ELSE 0 END), 0) avail
        FROM position_type pt
        LEFT JOIN employee e ON e.position_type_id=pt.id AND e.is_deleted=0
        LEFT JOIN employee_status es ON e.status_id=es.id
        WHERE pt.is_deleted=0
        GROUP BY pt.id ORDER BY pt.name
        """,
    )


# ==================== Требования ====================


def requirement_stats(db: Session) -> Row:
    return {
        "total": int(_scalar(db, "SELECT COUNT(*) FROM requirement WHERE is_deleted=0") or 0),
        "criteria": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM requirement
                WHERE is_deleted=0 AND acceptance_criteria IS NOT NULL AND acceptance_criteria <> ''
                """,
            )
            or 0
        ),
        "implemented": int(
            _scalar(
                db,
                """
                SELECT COUNT(DISTINCT r.id) FROM requirement r
                WHERE r.is_deleted=0 AND EXISTS (
                    SELECT 1 FROM task t WHERE t.requirement_id=r.id AND t.is_deleted=0)
                """,
            )
            or 0
        ),
    }


def requirements_by_project(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT p.id, p.name, COUNT(r.id) total,
               COALESCE(SUM(CASE WHEN r.acceptance_criteria IS NOT NULL
                                 AND r.acceptance_criteria <> '' THEN 1 ELSE 0 END), 0) crit,
               COALESCE(SUM(CASE WHEN EXISTS (
                   SELECT 1 FROM task t WHERE t.requirement_id=r.id AND t.is_deleted=0)
                   THEN 1 ELSE 0 END), 0) impl
        FROM project p LEFT JOIN requirement r ON r.project_id=p.id AND r.is_deleted=0
        WHERE p.is_deleted=0 GROUP BY p.id ORDER BY p.name
        """,
    )


def requirements_by_type(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT rt.name, COUNT(r.id) cnt FROM requirement_type rt
        LEFT JOIN requirement r ON r.requirement_type_id=rt.id AND r.is_deleted=0
        WHERE rt.is_deleted=0 GROUP BY rt.id ORDER BY rt.name
        """,
    )


def requirements_by_priority(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT pr.name, COUNT(r.id) cnt FROM priority pr
        LEFT JOIN requirement r ON r.priority_id=pr.id AND r.is_deleted=0
        WHERE pr.is_deleted=0 GROUP BY pr.id ORDER BY pr.weight
        """,
    )


# ==================== Этапы ====================


def stage_stats(db: Session) -> Row:
    return {
        "total": int(_scalar(db, "SELECT COUNT(*) FROM project_stage WHERE is_deleted=0") or 0),
        "done": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
                WHERE ps.is_deleted=0 AND pss.name='Завершён'
                """,
            )
            or 0
        ),
        "work": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
                WHERE ps.is_deleted=0 AND pss.name='В работе'
                """,
            )
            or 0
        ),
        "overdue": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
                WHERE ps.is_deleted=0 AND ps.planned_end < date('now')
                  AND pss.name NOT IN ('Завершён', 'Отменён')
                """,
            )
            or 0
        ),
    }


def stages_by_project(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT p.id, p.name, COUNT(ps.id) total,
               SUM(CASE WHEN pss.name='Завершён' THEN 1 ELSE 0 END) done,
               SUM(CASE WHEN pss.name='В работе' THEN 1 ELSE 0 END) work,
               SUM(CASE WHEN ps.planned_end < date('now')
                        AND pss.name NOT IN ('Завершён', 'Отменён') THEN 1 ELSE 0 END) over
        FROM project p
        LEFT JOIN project_stage ps ON ps.project_id=p.id AND ps.is_deleted=0
        LEFT JOIN project_stage_status pss ON ps.status_id=pss.id
        WHERE p.is_deleted=0 GROUP BY p.id ORDER BY p.name
        """,
    )


# ==================== Задачи ====================


def task_stats(db: Session) -> Row:
    return {
        "total": int(_scalar(db, "SELECT COUNT(*) FROM task WHERE is_deleted=0") or 0),
        "done": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM task t JOIN task_status ts ON t.status_id=ts.id
                WHERE t.is_deleted=0 AND ts.name='Выполнена'
                """,
            )
            or 0
        ),
        "work": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM task t JOIN task_status ts ON t.status_id=ts.id
                WHERE t.is_deleted=0 AND ts.name IN ('Новая', 'В работе')
                """,
            )
            or 0
        ),
        "overdue": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM task t JOIN task_status ts ON t.status_id=ts.id
                WHERE t.is_deleted=0 AND t.deadline < date('now')
                  AND ts.name NOT IN ('Выполнена', 'Отменена')
                """,
            )
            or 0
        ),
        "noexec": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM task t WHERE t.is_deleted=0 AND NOT EXISTS (
                    SELECT 1 FROM task_assignment ta
                    WHERE ta.task_id=t.id AND ta.task_kind='task' AND ta.is_deleted=0)
                """,
            )
            or 0
        ),
    }


def tasks_by_status(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT ts.name, ts.color, COUNT(t.id) cnt FROM task_status ts
        LEFT JOIN task t ON t.status_id=ts.id AND t.is_deleted=0
        WHERE ts.is_deleted=0 GROUP BY ts.id ORDER BY ts.id
        """,
    )


def tasks_by_priority(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT pr.name, COUNT(t.id) cnt FROM priority pr
        LEFT JOIN task t ON t.priority_id=pr.id AND t.is_deleted=0
        WHERE pr.is_deleted=0 GROUP BY pr.id ORDER BY pr.weight
        """,
    )


def tasks_without_executor(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT t.id, t.description, pr.name prio, ts.name st,
               p.id pid, p.name pname, ps.id stage_id, pst.name stype
        FROM task t
        JOIN priority pr ON t.priority_id=pr.id
        JOIN task_status ts ON t.status_id=ts.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN project_stage_type pst ON ps.stage_type_id=pst.id
        LEFT JOIN project p ON p.id = COALESCE(
            ps.project_id, (SELECT project_id FROM requirement WHERE id=t.requirement_id))
        WHERE t.is_deleted=0 AND NOT EXISTS (
            SELECT 1 FROM task_assignment ta
            WHERE ta.task_id=t.id AND ta.task_kind='task' AND ta.is_deleted=0)
        """,
    )


# ==================== Подзадачи ====================


def subtask_stats(db: Session) -> Row:
    return {
        "total": int(_scalar(db, "SELECT COUNT(*) FROM subtask WHERE is_deleted=0") or 0),
        "done": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM subtask s JOIN task_status ts ON s.status_id=ts.id
                WHERE s.is_deleted=0 AND ts.name='Выполнена'
                """,
            )
            or 0
        ),
        "work": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM subtask s JOIN task_status ts ON s.status_id=ts.id
                WHERE s.is_deleted=0 AND ts.name IN ('Новая', 'В работе')
                """,
            )
            or 0
        ),
        "overdue": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM subtask s JOIN task_status ts ON s.status_id=ts.id
                WHERE s.is_deleted=0 AND s.deadline < date('now')
                  AND ts.name NOT IN ('Выполнена', 'Отменена')
                """,
            )
            or 0
        ),
        "noexec": int(
            _scalar(
                db,
                """
                SELECT COUNT(*) FROM subtask s WHERE s.is_deleted=0 AND NOT EXISTS (
                    SELECT 1 FROM task_assignment ta
                    WHERE ta.task_id=s.id AND ta.task_kind='subtask' AND ta.is_deleted=0)
                """,
            )
            or 0
        ),
    }


def subtasks_by_status(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT ts.name, ts.color, COUNT(s.id) cnt FROM task_status ts
        LEFT JOIN subtask s ON s.status_id=ts.id AND s.is_deleted=0
        WHERE ts.is_deleted=0 GROUP BY ts.id ORDER BY ts.id
        """,
    )


def subtasks_without_executor(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT s.id, t.id parent_id, t.description parent, s.description, pr.name prio, ts.name st
        FROM subtask s
        JOIN task t ON s.parent_task_id=t.id
        JOIN priority pr ON s.priority_id=pr.id
        JOIN task_status ts ON s.status_id=ts.id
        WHERE s.is_deleted=0 AND NOT EXISTS (
            SELECT 1 FROM task_assignment ta
            WHERE ta.task_id=s.id AND ta.task_kind='subtask' AND ta.is_deleted=0)
        """,
    )


# ==================== Назначения ====================


def assignment_stats(db: Session) -> Row:
    return {
        "total": int(_scalar(db, "SELECT COUNT(*) FROM task_assignment WHERE is_deleted=0") or 0),
        "task": int(_scalar(db, "SELECT COUNT(*) FROM task_assignment WHERE is_deleted=0 AND task_kind='task'") or 0),
        "subtask": int(
            _scalar(db, "SELECT COUNT(*) FROM task_assignment WHERE is_deleted=0 AND task_kind='subtask'") or 0
        ),
    }


def assignments_by_employee(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT e.id, e.last_name, e.first_name, pt.name pos,
               COALESCE(SUM(CASE WHEN ta.task_kind='task' THEN ta.share ELSE 0 END), 0) task_share,
               COALESCE(SUM(CASE WHEN ta.task_kind='subtask' THEN ta.share ELSE 0 END), 0) sub_share,
               COUNT(ta.id) acnt
        FROM employee e
        LEFT JOIN task_assignment ta ON ta.employee_id=e.id AND ta.is_deleted=0
        JOIN position_type pt ON e.position_type_id=pt.id
        WHERE e.is_deleted=0
        GROUP BY e.id ORDER BY (task_share + sub_share) DESC
        """,
    )


# ==================== События ====================


def event_stats(db: Session) -> Row:
    return {
        "total": int(_scalar(db, "SELECT COUNT(*) FROM event WHERE is_deleted=0") or 0),
        "last30": int(
            _scalar(
                db,
                "SELECT COUNT(*) FROM event WHERE is_deleted=0 AND occurred_at >= date('now', '-30 days')",
            )
            or 0
        ),
    }


def events_by_month(db: Session) -> list[Row]:
    return _rows(
        db,
        """
        SELECT strftime('%Y-%m', occurred_at) m, COUNT(*) cnt
        FROM event WHERE is_deleted=0 GROUP BY m ORDER BY m DESC
        """,
    )


def recent_events(db: Session) -> list[Row]:
    return _rows(
        db,
        "SELECT * FROM event WHERE is_deleted=0 ORDER BY occurred_at DESC LIMIT 10",
    )
