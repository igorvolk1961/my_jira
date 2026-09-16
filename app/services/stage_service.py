"""Этапы проектов: бизнес-логика и сборка дерева проекта."""

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import employee_repo, stage_repo

Row = dict[str, Any]
Tree = dict[str, Any]


def _to_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _to_date(value: Any) -> date | None:
    text = str(value).strip() if value else ""
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def list_stages(db: Session) -> list[Row]:
    return stage_repo.list_all(db)


def detail(db: Session, stage_id: int) -> tuple[Row | None, list[Row]]:
    stage = stage_repo.get_detail(db, stage_id)
    if stage is None:
        return None, []
    return stage, stage_repo.list_tasks(db, stage_id)


def form_options(db: Session) -> dict[str, list[Row]]:
    return stage_repo.form_options(db)


def _build_values(form: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    project_id = _to_int(form.get("project_id"))
    stage_type_id = _to_int(form.get("stage_type_id"))
    status_id = _to_int(form.get("status_id"))
    if not project_id or not stage_type_id or not status_id:
        return {}, "Заполните обязательные поля этапа"
    values: dict[str, Any] = {
        "project_id": project_id,
        "stage_type_id": stage_type_id,
        "status_id": status_id,
        "planned_end": _to_date(form.get("planned_end")),
    }
    return values, ""


def create(db: Session, form: Mapping[str, Any]) -> str:
    values, error = _build_values(form)
    if error:
        return error
    stage_repo.create(db, values)
    return ""


def update(db: Session, stage_id: int, form: Mapping[str, Any]) -> str:
    item = stage_repo.get(db, stage_id)
    if item is None:
        return "Этап не найден"
    values, error = _build_values(form)
    if error:
        return error
    stage_repo.update(db, item, values)
    return ""


def delete(db: Session, stage_id: int) -> None:
    stage_repo.soft_delete(db, stage_id)


def project_tree(db: Session, project_id: int) -> Tree:
    """Дерево этапы → задачи → подзадачи с назначениями (для карточки проекта)."""
    data = stage_repo.tree_rows(db, project_id)
    stages = data["stages"]
    tasks = data["tasks"]
    subtasks = data["subtasks"]
    assignments = data["assignments"]

    sub_children: dict[int, list[Row]] = {}
    top_by_task: dict[int, list[Row]] = {}
    for subtask in subtasks:
        parent_subtask = subtask["parent_subtask_id"]
        if parent_subtask is None:
            top_by_task.setdefault(int(subtask["parent_task_id"]), []).append(subtask)
        else:
            sub_children.setdefault(int(parent_subtask), []).append(subtask)

    grouped: dict[tuple[str, int], list[Row]] = {}
    for assignment in assignments:
        grouped.setdefault((str(assignment["task_kind"]), int(assignment["task_id"])), []).append(assignment)

    covered = employee_repo.covered_for_employees(db, {int(assignment["employee_id"]) for assignment in assignments})
    filtered: dict[tuple[str, int], list[Row]] = {
        key: [a for a in rows if key not in covered.get(int(a["employee_id"]), set())] for key, rows in grouped.items()
    }

    def build_subtask(subtask: Row) -> Row:
        return {
            **subtask,
            "assignments": filtered.get(("subtask", int(subtask["id"])), []),
            "children": [build_subtask(child) for child in sub_children.get(int(subtask["id"]), [])],
        }

    def build_task(task: Row) -> Row:
        return {
            **task,
            "assignments": filtered.get(("task", int(task["id"])), []),
            "subtasks": [build_subtask(s) for s in top_by_task.get(int(task["id"]), [])],
        }

    tasks_by_stage: dict[int, list[Row]] = {}
    for task in tasks:
        stage_id = task["stage_id"]
        if stage_id is None:
            continue
        tasks_by_stage.setdefault(int(stage_id), []).append(task)

    built_stages: list[Row] = [
        {**stage, "tasks": [build_task(t) for t in tasks_by_stage.get(int(stage["id"]), [])]} for stage in stages
    ]
    return {"stages": built_stages, "count": len(stages)}
