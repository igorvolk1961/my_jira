"""Главная страница: сводные показатели и выбор текущего проекта."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def dashboard_stats(db: Session) -> dict[str, int]:
    return {
        "projects": db.execute(text("SELECT COUNT(*) FROM project WHERE is_deleted=0")).scalar_one(),
        "tasks": db.execute(text("SELECT COUNT(*) FROM task WHERE is_deleted=0")).scalar_one(),
        "employees": db.execute(text("SELECT COUNT(*) FROM employee WHERE is_deleted=0")).scalar_one(),
        "events": db.execute(text("SELECT COUNT(*) FROM event WHERE is_deleted=0")).scalar_one(),
        "active_tasks": db.execute(
            text(
                "SELECT COUNT(*) FROM task t JOIN task_status ts ON t.status_id = ts.id"
                " WHERE t.is_deleted=0 AND ts.name IN ('Новая', 'В работе')"
            )
        ).scalar_one(),
        "overdue_tasks": db.execute(
            text(
                "SELECT COUNT(*) FROM task WHERE is_deleted=0 AND deadline < date('now')"
                " AND status_id NOT IN (SELECT id FROM task_status WHERE name IN ('Выполнена', 'Отменена'))"
            )
        ).scalar_one(),
    }
