"""Построение HTML-данных для страниц задач и подзадач (без SQL)."""

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


def _options(
    rows: list[dict[str, Any]],
    label: Any,
    selected: Any = None,
    empty: str | None = None,
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if empty is not None:
        options.append({"value": "", "label": empty, "selected": selected in (None, "", 0)})
    for row in rows:
        selected_flag = selected is not None and str(row["id"]) == str(selected)
        options.append({"value": str(row["id"]), "label": label(row), "selected": selected_flag})
    return options


def status_form_html(
    request: Request,
    endpoint: str,
    entity_id: int,
    statuses: list[dict[str, Any]],
    selected_id: Any,
    back: str | None = None,
    label: str = "Сменить статус",
) -> str:
    action = url_or(request, endpoint, "#", id=entity_id)
    options = "".join(
        f'<option value="{s["id"]}"{" selected" if s["id"] == selected_id else ""}>{_esc(s["name"])}</option>'
        for s in statuses
    )
    next_field = f'<input type="hidden" name="next" value="{_esc(back)}">' if back else ""
    return (
        f'<form method="POST" action="{action}" '
        f'style="display:inline-flex; gap:6px; align-items:center; margin:5px;">'
        f'<select name="status_id">{options}</select>{next_field}'
        f'<button type="submit" class="btn btn-success" style="margin:0;">{_esc(label)}</button></form>'
    )


def _status_badge(status_name: Any, color: Any) -> str:
    return f'<span class="badge" style="background: {color or "#95a5a6"}">{_esc(status_name)}</span>'


def task_table(request: Request, rows: list[dict[str, Any]], can_write: bool) -> dict[str, Any]:
    headers = ["ID", "Проект", "Описание", "Тип", "Этап", "Приоритет", "Срок", "Статус", "Действия"]
    table_rows: list[list[str]] = []
    for row in rows:
        if row["project_id"]:
            project = f'<a href="{url_or(request, "project_detail", "#", id=row["project_id"])}">{_esc(row["project_name"])}</a>'
        else:
            project = "-"
        if row["stage_id"]:
            stage = f'<a href="{url_or(request, "project_stage_detail", "#", id=row["stage_id"])}">{_esc(row["stage_name"])}</a>'
        else:
            stage = "-"
        actions = f'<a href="{url_or(request, "task_detail", "#", id=row["id"])}" class="btn btn-success">Открыть</a>'
        if can_write:
            actions += (
                f' <a href="{url_or(request, "task_edit", "#", id=row["id"])}" class="btn btn-primary">Изменить</a>'
                f' <a href="{url_or(request, "task_delete", "#", id=row["id"])}" class="btn btn-danger"'
                " onclick=\"return confirm('Удалить?')\">Удалить</a>"
            )
        table_rows.append(
            [
                str(row["id"]),
                project,
                _esc((row["description"] or "")[:40]) + "...",
                _text(row["type_name"]),
                stage,
                _esc(row["priority_name"]),
                _text(row["deadline"]),
                _status_badge(row["status_name"], row.get("status_color")),
                actions,
            ]
        )
    return {"title": "Задачи", "headers": headers, "rows": table_rows}


def subtask_table(request: Request, rows: list[dict[str, Any]]) -> dict[str, Any]:
    headers = ["ID", "Родительская задача", "Описание", "Приоритет", "Срок", "Статус", "Действия"]
    table_rows: list[list[str]] = []
    for row in rows:
        parent = (
            f'<a href="{url_or(request, "task_detail", "#", id=row["parent_task_id"])}">'
            f"{_esc((row['parent_desc'] or '')[:40])}...</a>"
        )
        actions = (
            f'<a href="{url_or(request, "subtask_detail", "#", id=row["id"])}" class="btn btn-success">Открыть</a>'
            f' <a href="{url_or(request, "subtask_edit", "#", id=row["id"])}" class="btn btn-primary">Изменить</a>'
            f' <a href="{url_or(request, "subtask_delete", "#", id=row["id"])}" class="btn btn-danger"'
            " onclick=\"return confirm('Удалить?')\">Удалить</a>"
        )
        table_rows.append(
            [
                str(row["id"]),
                parent,
                _esc((row["description"] or "")[:40]) + "...",
                _esc(row["priority_name"]),
                _text(row["deadline"]),
                _status_badge(row["status_name"], row.get("status_color")),
                actions,
            ]
        )
    return {"title": "Подзадачи", "headers": headers, "rows": table_rows}


def task_form_fields(
    request: Request,
    *,
    requirements: list[dict[str, Any]],
    stages: list[dict[str, Any]],
    priorities: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    task_types: list[dict[str, Any]],
    task: dict[str, Any] | None = None,
    preset_stage_id: Any = None,
    preset_requirement_id: Any = None,
    origin: str | None = None,
) -> list[dict[str, Any]]:
    values = task or {}
    if preset_stage_id is None:
        preset_stage_id = values.get("stage_id")
    if preset_requirement_id is None:
        preset_requirement_id = values.get("requirement_id")
    return [
        {"name": "origin", "type": "hidden", "value": origin or ""},
        {
            "name": "requirement_id",
            "label": "Требование",
            "type": "select",
            "required": True,
            "options": _options(
                requirements,
                lambda r: f"[{r['project_name']}] {(r['description'] or '')[:50]}",
                preset_requirement_id,
                "— выберите требование —",
            ),
        },
        {
            "name": "description",
            "label": "Описание",
            "type": "textarea",
            "required": True,
            "value": values.get("description") or "",
        },
        {
            "name": "task_type_id",
            "label": "Тип задачи",
            "type": "select",
            "required": True,
            "options": _options(task_types, lambda r: r["name"], values.get("task_type_id")),
        },
        {
            "name": "stage_id",
            "label": "Этап проекта",
            "type": "select",
            "required": True,
            "options": _options(
                stages,
                lambda r: f"[{r['project_name']}] {r['type_name']}",
                preset_stage_id,
                "— выберите этап —",
            ),
        },
        {
            "name": "priority_id",
            "label": "Приоритет",
            "type": "select",
            "required": True,
            "options": _options(priorities, lambda r: r["name"], values.get("priority_id")),
        },
        {
            "name": "deadline",
            "label": "Срок исполнения",
            "type": "date",
            "value": values.get("deadline") or "",
        },
        {
            "name": "status_id",
            "label": "Статус",
            "type": "select",
            "required": True,
            "options": _options(statuses, lambda r: r["name"], values.get("status_id")),
        },
    ]


def subtask_form_fields(
    request: Request,
    *,
    tasks: list[dict[str, Any]],
    subtasks: list[dict[str, Any]],
    stages: list[dict[str, Any]],
    priorities: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    subtask: dict[str, Any] | None = None,
    preset_task_id: Any = None,
    preset_subtask_id: Any = None,
    preset_stage_id: Any = None,
    origin: str | None = None,
) -> list[dict[str, Any]]:
    values = subtask or {}
    if preset_task_id is None:
        preset_task_id = values.get("parent_task_id")
    if preset_subtask_id is None:
        preset_subtask_id = values.get("parent_subtask_id")
    if preset_stage_id is None:
        preset_stage_id = values.get("stage_id")
    return [
        {"name": "origin", "type": "hidden", "value": origin or ""},
        {
            "name": "parent_subtask_id",
            "label": "Родительская подзадача",
            "type": "select",
            "options": _options(
                subtasks,
                lambda r: f"{r['id']}. {(r['description'] or '')[:50]}",
                preset_subtask_id,
                "— нет, подзадача напрямую от задачи —",
            ),
        },
        {
            "name": "parent_task_id",
            "label": "Родительская задача",
            "type": "select",
            "required": True,
            "options": _options(
                tasks,
                lambda r: f"{r['id']}. {(r['description'] or '')[:50]}",
                preset_task_id,
            ),
        },
        {
            "name": "description",
            "label": "Описание",
            "type": "textarea",
            "required": True,
            "value": values.get("description") or "",
        },
        {
            "name": "stage_id",
            "label": "Этап проекта",
            "type": "select",
            "options": _options(
                stages,
                lambda r: f"[{r['project_name']}] {r['type_name']}",
                preset_stage_id,
                "Не выбран",
            ),
        },
        {
            "name": "priority_id",
            "label": "Приоритет",
            "type": "select",
            "required": True,
            "options": _options(priorities, lambda r: r["name"], values.get("priority_id")),
        },
        {
            "name": "deadline",
            "label": "Срок исполнения",
            "type": "date",
            "value": values.get("deadline") or "",
        },
        {
            "name": "status_id",
            "label": "Статус",
            "type": "select",
            "required": True,
            "options": _options(statuses, lambda r: r["name"], values.get("status_id")),
        },
    ]


def _executor_rows(request: Request, executors: list[dict[str, Any]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for executor in executors:
        rows.append(
            [
                f'<a href="{url_or(request, "employee_detail", "#", id=executor["eid"])}">'
                f"{_esc(executor['last_name'])} {_esc(executor['first_name'])}</a>",
                _text(executor["pos"]),
                f"{round(float(executor['share']) * 100)}%",
                f"{_esc(executor['assigner'] or '—')} "
                f'<span class="muted">({_esc(executor["assigned_at"] or "—")})</span>',
            ]
        )
    return rows


def _comment_rows(request: Request, comments: list[dict[str, Any]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for comment in comments:
        rows.append(
            [
                _esc(comment["created_at"]),
                _text(comment["author"]),
                _esc(comment["text"]),
                f'<a href="{url_or(request, "comment_delete", "#", id=comment["id"])}" class="btn btn-danger"'
                " onclick=\"return confirm('Удалить?')\">Удалить</a>",
            ]
        )
    return rows


def task_detail_context(request: Request, data: dict[str, Any]) -> dict[str, Any]:
    task = data["task"]
    info = [
        ("Задача", f"#{task['id']}"),
        (
            "Проект",
            f'<a href="{url_or(request, "project_detail", "#", id=task["pid"])}">{_esc(task["pname"])}</a>'
            if task["pid"]
            else "-",
        ),
        (
            "Этап",
            f'<a href="{url_or(request, "project_stage_detail", "#", id=task["stage_id"])}">{_esc(task["stype"])}</a>'
            if task["stage_id"]
            else "-",
        ),
        ("Описание", _esc(task["description"])),
        ("Тип", _text(task["type_name"])),
        ("Приоритет", _esc(task["prio"])),
        ("Срок", _text(task["deadline"])),
        ("Статус", _status_badge(task["st"], task.get("color"))),
        (
            "Требование",
            f'<a href="{url_or(request, "requirement_detail", "#", id=task["requirement_id"])}">'
            f"{_esc(task['req_desc'])}</a>"
            if task["requirement_id"]
            else "-",
        ),
    ]
    subtask_rows = [
        [
            f'<a href="{url_or(request, "subtask_detail", "#", id=s["id"])}">#{s["id"]}</a>',
            _esc((s["description"] or "")[:60]),
            _esc(s["prio"]),
            _text(s["deadline"]),
            _status_badge(s["st"], s.get("color")),
        ]
        for s in data["subtasks"]
    ]
    add_subtask = (
        f'<a href="{url_or(request, "subtask_create", "#", parent_task_id=task["id"])}" '
        'class="btn btn-success">+ Подзадача</a>'
    )
    add_comment = (
        f'<a href="{url_or(request, "comment_create", "#", entity_type="task", entity_id=task["id"])}" '
        'class="btn btn-success">+ Комментарий</a>'
    )
    add_requirement = (
        f'<a href="{url_or(request, "requirement_create", "#", project_id=task["pid"], task_id=task["id"])}" '
        'class="btn btn-success">+ Требование</a>'
        if task["pid"]
        else ""
    )
    add_assignment = (
        f'<a href="{url_or(request, "task_assignment_create", "#", task_id=task["id"], task_kind="task", origin=task["pid"])}" '
        'class="btn btn-warning">Назначить</a>'
        if task["pid"]
        else ""
    )
    status_html = ""
    if data["can_status"]:
        status_html = status_form_html(request, "task_status_change", task["id"], data["statuses"], task["status_id"])
    return {
        "title": f"Задача #{task['id']}",
        "info": info,
        "tables": [
            {
                "title": "Кто выполняет",
                "headers": ["Сотрудник", "Должность", "Доля", "Назначил"],
                "rows": _executor_rows(request, data["executors"]),
            },
            {
                "title": "Подзадачи " + add_subtask,
                "headers": ["ID", "Описание", "Приоритет", "Срок", "Статус"],
                "rows": subtask_rows,
            },
            {
                "title": "Комментарии " + add_comment,
                "headers": ["Дата", "Автор", "Текст", "Действия"],
                "rows": _comment_rows(request, data["comments"]),
            },
        ],
        "actions": add_requirement + " " + add_assignment + " " + status_html,
    }


def subtask_detail_context(request: Request, data: dict[str, Any]) -> dict[str, Any]:
    subtask = data["subtask"]
    info = [
        ("Подзадача", f"#{subtask['id']}"),
        (
            "Родительская задача",
            f'<a href="{url_or(request, "task_detail", "#", id=subtask["parent_id"])}">'
            f"#{subtask['parent_id']} {_esc((subtask['parent_desc'] or '')[:40])}</a>",
        ),
        ("Описание", _esc(subtask["description"])),
        ("Приоритет", _esc(subtask["prio"])),
        ("Срок", _text(subtask["deadline"])),
        ("Статус", _status_badge(subtask["st"], subtask.get("color"))),
    ]
    add_comment = (
        f'<a href="{url_or(request, "comment_create", "#", entity_type="subtask", entity_id=subtask["id"])}" '
        'class="btn btn-success">+ Комментарий</a>'
    )
    add_subtask = (
        f'<a href="{url_or(request, "subtask_create", "#", parent_subtask_id=subtask["id"])}" '
        'class="btn btn-success">+ Подзадача</a>'
    )
    add_assignment = (
        f'<a href="{url_or(request, "task_assignment_create", "#", task_id=subtask["id"], task_kind="subtask", origin=data["project_id"])}" '
        'class="btn btn-warning">Назначить</a>'
        if data["project_id"]
        else ""
    )
    status_html = ""
    if data["can_status"]:
        status_html = status_form_html(
            request, "subtask_status_change", subtask["id"], data["statuses"], subtask["status_id"]
        )
    children_rows = [
        [
            f'<a href="{url_or(request, "subtask_detail", "#", id=c["id"])}">#{c["id"]}</a>',
            _esc((c["description"] or "")[:60]),
        ]
        for c in data["children"]
    ]
    return {
        "title": f"Подзадача #{subtask['id']}",
        "info": info,
        "tables": [
            {
                "title": "Кто выполняет",
                "headers": ["Сотрудник", "Должность", "Доля", "Назначил"],
                "rows": _executor_rows(request, data["executors"]),
            },
            {
                "title": "Вложенные подзадачи " + add_subtask,
                "headers": ["ID", "Описание"],
                "rows": children_rows,
            },
            {
                "title": "Комментарии " + add_comment,
                "headers": ["Дата", "Автор", "Текст", "Действия"],
                "rows": _comment_rows(request, data["comments"]),
            },
        ],
        "actions": add_assignment + " " + status_html,
    }
