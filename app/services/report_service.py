"""Сервис отчётов: бизнес-агрегация (без HTML и FastAPI)."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories import employee_repo, report_repo

Row = dict[str, Any]


def quadrant(influence: int, interest: int) -> str:
    if influence >= 4 and interest >= 4:
        return "Ключевые игроки"
    if influence >= 4:
        return "Удовлетворять"
    if interest >= 4:
        return "Держать в курсе"
    return "Наблюдать"


def projects(db: Session) -> Row:
    stats = report_repo.project_stats(db)
    by_priority = report_repo.projects_by_priority(db)
    total = stats["total"]
    avg_prio = sum(p["weight"] * p["cnt"] for p in by_priority) / total if total else 0.0
    return {
        "total": total,
        "cost": stats["cost"],
        "budget": stats["budget"],
        "avg_priority": avg_prio,
        "by_priority": by_priority,
        "progress": report_repo.project_progress(db),
    }


def stakeholders(db: Session) -> Row:
    types = report_repo.stakeholder_types(db)
    for item in types:
        item["quadrant"] = quadrant(int(item["inf"]), int(item["ints"]))
    key = sum(1 for item in types if item["quadrant"] == "Ключевые игроки")
    return {
        "total": report_repo.stakeholder_total(db),
        "types": types,
        "key": key,
    }


def employees(db: Session) -> Row:
    stats = report_repo.employee_stats(db)
    load = report_repo.employee_load(db)
    loads = employee_repo.effective_loads(db, {int(item["id"]) for item in load})
    for item in load:
        item["load"] = loads.get(int(item["id"]), 0.0)
    overloaded = sum(1 for item in load if item["load"] > 1.0)
    return {
        "total": stats["total"],
        "available": stats["available"],
        "assigned": stats["assigned"],
        "overloaded": overloaded,
        "load": load,
        "by_position": report_repo.employees_by_position(db),
    }


def requirements(db: Session) -> Row:
    stats = report_repo.requirement_stats(db)
    return {
        "total": stats["total"],
        "criteria": stats["criteria"],
        "implemented": stats["implemented"],
        "by_project": report_repo.requirements_by_project(db),
        "by_type": report_repo.requirements_by_type(db),
        "by_priority": report_repo.requirements_by_priority(db),
    }


def stages(db: Session) -> Row:
    stats = report_repo.stage_stats(db)
    return {
        "total": stats["total"],
        "done": stats["done"],
        "work": stats["work"],
        "overdue": stats["overdue"],
        "by_project": report_repo.stages_by_project(db),
    }


def tasks(db: Session) -> Row:
    stats = report_repo.task_stats(db)
    return {
        "total": stats["total"],
        "done": stats["done"],
        "work": stats["work"],
        "overdue": stats["overdue"],
        "noexec": stats["noexec"],
        "by_status": report_repo.tasks_by_status(db),
        "by_priority": report_repo.tasks_by_priority(db),
        "without_executor": report_repo.tasks_without_executor(db),
    }


def subtasks(db: Session) -> Row:
    stats = report_repo.subtask_stats(db)
    return {
        "total": stats["total"],
        "done": stats["done"],
        "work": stats["work"],
        "overdue": stats["overdue"],
        "noexec": stats["noexec"],
        "by_status": report_repo.subtasks_by_status(db),
        "without_executor": report_repo.subtasks_without_executor(db),
    }


def assignments(db: Session) -> Row:
    stats = report_repo.assignment_stats(db)
    by_employee = report_repo.assignments_by_employee(db)
    loads = employee_repo.effective_loads(db, {int(item["id"]) for item in by_employee})
    for item in by_employee:
        item["load"] = loads.get(int(item["id"]), 0.0)
    max_load = max((item["load"] for item in by_employee), default=0.0)
    return {
        "total": stats["total"],
        "task": stats["task"],
        "subtask": stats["subtask"],
        "max_load": max_load,
        "by_employee": by_employee,
    }


def events(db: Session) -> Row:
    stats = report_repo.event_stats(db)
    recent = report_repo.recent_events(db)
    return {
        "total": stats["total"],
        "last30": stats["last30"],
        "last_event": recent[0]["occurred_at"] if recent else None,
        "months": report_repo.events_by_month(db),
        "recent": recent,
    }
