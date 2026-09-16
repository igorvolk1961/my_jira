"""Построение HTML-данных для страниц назначений (без SQL)."""

import html
from typing import Any

from fastapi import Request

from app.presentation.urls import url_or


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _text(value: Any, dash: str = "-") -> str:
    if value is None or value == "":
        return dash
    return _esc(value)


def assignment_table(request: Request, rows: list[dict[str, Any]]) -> dict[str, Any]:
    headers = ["ID", "Тип", "Задача", "Сотрудник", "Доля", "Действия"]
    table_rows: list[list[str]] = []
    for row in rows:
        kind_label = "Задача" if row["task_kind"] == "task" else "Подзадача"
        endpoint = "task_detail" if row["task_kind"] == "task" else "subtask_detail"
        task_cell = (
            f'<a href="{url_or(request, endpoint, "#", id=row["task_id"])}">'
            f"{_esc((row['task_desc'] or '')[:40])}...</a>"
        )
        employee_cell = (
            f'<a href="{url_or(request, "employee_detail", "#", id=row["employee_id"])}">'
            f"{_esc(row['last_name'])} {_esc(row['first_name'])}</a>"
        )
        actions = (
            f'<a href="{url_or(request, "task_assignment_detail", "#", id=row["id"])}" class="btn btn-success">Открыть</a>'
            f' <a href="{url_or(request, "task_assignment_edit", "#", id=row["id"])}" class="btn btn-primary">Изменить</a>'
            f' <a href="{url_or(request, "task_assignment_delete", "#", id=row["id"])}" class="btn btn-danger"'
            " onclick=\"return confirm('Удалить?')\">Удалить</a>"
        )
        table_rows.append(
            [
                str(row["id"]),
                _esc(kind_label),
                task_cell,
                employee_cell,
                f"{round(float(row['share']) * 100)}%",
                actions,
            ]
        )
    return {"title": "Назначения задач", "headers": headers, "rows": table_rows}


def assignment_detail_context(request: Request, row: dict[str, Any]) -> dict[str, Any]:
    endpoint = "task_detail" if row["task_kind"] == "task" else "subtask_detail"
    task_html = (
        f'<a href="{url_or(request, endpoint, "#", id=row["task_id"])}">{_esc(row["task_desc"])}</a>'
        if row["task_desc"]
        else "-"
    )
    info = [
        ("Назначение", f"#{row['id']}"),
        ("Тип", "Задача" if row["task_kind"] == "task" else "Подзадача"),
        ("Задача", task_html),
        ("Сотрудник", f"{_esc(row['last_name'])} {_esc(row['first_name'])}"),
        ("Должность", _text(row["pos"])),
        ("Доля", f"{round(float(row['share']) * 100)}%"),
    ]
    return {"title": f"Назначение #{row['id']}", "info": info, "tables": [], "actions": ""}


def _task_options(
    tasks: list[dict[str, Any]],
    subtasks: list[dict[str, Any]],
    selected_id: Any,
    selected_kind: Any,
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for task in tasks:
        options.append(
            {
                "value": str(task["id"]),
                "label": f"Задача: {(task['description'] or '')[:50]}",
                "selected": str(task["id"]) == str(selected_id) and selected_kind == "task",
            }
        )
    for subtask in subtasks:
        options.append(
            {
                "value": str(subtask["id"]),
                "label": f"Подзадача: {(subtask['description'] or '')[:50]}",
                "selected": str(subtask["id"]) == str(selected_id) and selected_kind == "subtask",
            }
        )
    return options


def _employee_options(
    employees: list[dict[str, Any]],
    selected_id: Any = None,
    include_empty: str | None = None,
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if include_empty is not None:
        options.append({"value": "", "label": include_empty, "selected": selected_id in (None, "")})
    for employee in employees:
        options.append(
            {
                "value": str(employee["id"]),
                "label": f"{employee['last_name']} {employee['first_name']}",
                "selected": selected_id is not None and str(employee["id"]) == str(selected_id),
            }
        )
    return options


def assignment_form_fields(
    *,
    tasks: list[dict[str, Any]],
    subtasks: list[dict[str, Any]],
    employees: list[dict[str, Any]],
    selected_task_id: Any = None,
    selected_kind: str = "task",
    selected_employee_id: Any = None,
    share: Any = "1.0",
    origin: str | None = None,
    task_kind_fixed: str | None = None,
    employee_required: bool = True,
    employee_empty_label: str | None = None,
) -> list[dict[str, Any]]:
    if task_kind_fixed is None:
        kind_field: dict[str, Any] = {
            "name": "task_kind",
            "label": "Тип задачи",
            "type": "select",
            "required": True,
            "options": [
                {"value": "task", "label": "Задача", "selected": selected_kind == "task"},
                {"value": "subtask", "label": "Подзадача", "selected": selected_kind == "subtask"},
            ],
        }
    else:
        kind_field = {"name": "task_kind", "type": "hidden", "value": task_kind_fixed}
    return [
        {"name": "origin", "type": "hidden", "value": origin or ""},
        kind_field,
        {
            "name": "task_id",
            "label": "Объект назначения",
            "type": "select",
            "required": True,
            "options": _task_options(tasks, subtasks, selected_task_id, selected_kind),
        },
        {
            "name": "employee_id",
            "label": "Сотрудник",
            "type": "select",
            "required": employee_required,
            "options": _employee_options(employees, selected_employee_id, employee_empty_label),
        },
        {
            "name": "share",
            "label": "Доля (0.0 - 1.0)",
            "type": "number",
            "required": True,
            "value": share,
        },
    ]
