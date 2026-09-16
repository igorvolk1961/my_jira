"""Построение HTML для страниц сотрудников (без SQL и бизнес-логики)."""

import html
from typing import Any

from fastapi import Request

from app.security import role_label

ROLE_LABELS = (("admin", "администратор"), ("user", "пользователь"))


def _url(request: Request, name: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return "#"


def _anchor(request: Request, name: str, label: str, css: str, **params: Any) -> str:
    url = _url(request, name, **params)
    return f'<a href="{html.escape(url)}" class="{css}">{html.escape(label)}</a>'


def _link(request: Request, name: str, label: str, **params: Any) -> str:
    url = _url(request, name, **params)
    if url == "#":
        return html.escape(label)
    return f'<a href="{html.escape(url)}">{html.escape(label)}</a>'


def _status_badge(name: Any, available: Any) -> str:
    color = "#27ae60" if available else "#e74c3c"
    return f'<span class="badge" style="background: {color}">{html.escape(str(name))}</span>'


def _role_cell(request: Request, employee: dict[str, Any], is_admin: bool, self_employee_id: int | None) -> str:
    if not employee.get("user_id"):
        return '<span class="muted">—</span>'
    if is_admin and employee["id"] != self_employee_id:
        url = _url(request, "employee_role_change", id=employee["id"])
        options = "".join(
            f'<option value="{value}"{" selected" if value == employee.get("user_role") else ""}>{label}</option>'
            for value, label in ROLE_LABELS
        )
        checked = " checked" if employee.get("user_analyst") else ""
        return (
            f'<form method="POST" action="{html.escape(url)}" '
            'style="display:inline-flex; gap:4px; align-items:center; margin:0; flex-wrap:wrap;">'
            f'<select name="role">{options}</select>'
            '<label style="white-space:nowrap;">'
            f'<input type="checkbox" name="is_analyst" value="1"{checked} '
            'style="width:auto; display:inline; margin-right:4px;">сист. аналитик</label>'
            '<button type="submit" class="btn btn-primary" style="margin:0;">OK</button></form>'
        )
    return html.escape(role_label(employee.get("user_role"), bool(employee.get("user_analyst"))))


def list_table(
    request: Request,
    employees: list[dict[str, Any]],
    is_admin: bool,
    self_employee_id: int | None,
) -> dict[str, Any]:
    rows: list[list[str]] = []
    for employee in employees:
        actions = [_anchor(request, "employee_detail", "Открыть", "btn btn-success", id=employee["id"])]
        if is_admin:
            actions.append(_anchor(request, "employee_edit", "Изменить", "btn btn-primary", id=employee["id"]))
            if employee["id"] != self_employee_id:
                actions.append(_anchor(request, "employee_delete", "Удалить", "btn btn-danger", id=employee["id"]))
        rows.append(
            [
                str(employee["id"]),
                html.escape(
                    f"{employee['last_name']} {employee['first_name']} {employee.get('middle_name') or ''}".strip()
                ),
                html.escape(str(employee.get("position_name") or "")),
                _status_badge(employee.get("status_name"), employee.get("is_available")),
                _role_cell(request, employee, is_admin, self_employee_id),
                str(employee.get("subordinates_total") or 0),
                str(employee.get("subordinates_available") or 0),
                " ".join(actions),
            ]
        )
    return {
        "title": "Сотрудники",
        "headers": [
            "ID",
            "ФИО",
            "Должность",
            "Статус",
            "Роль",
            "Всего подчинённых",
            "Доступно подчинённых",
            "Действия",
        ],
        "rows": rows,
    }


def _select_options(
    items: list[dict[str, Any]], selected: Any, label_key: str = "name", value_key: str = "id"
) -> list[dict[str, Any]]:
    return [
        {"value": item[value_key], "label": item[label_key], "selected": item[value_key] == selected} for item in items
    ]


def form_fields(
    employee: dict[str, Any] | None,
    positions: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    project_id: int | None = None,
    origin: int | None = None,
) -> list[dict[str, Any]]:
    def value(key: str, default: Any = "") -> Any:
        return employee.get(key, default) if employee else default

    fields: list[dict[str, Any]] = []
    if project_id:
        fields.append({"name": "project_id", "type": "hidden", "value": project_id})
    if origin:
        fields.append({"name": "origin", "type": "hidden", "value": origin})
    fields.extend(
        [
            {"name": "last_name", "label": "Фамилия", "type": "text", "required": True, "value": value("last_name")},
            {"name": "first_name", "label": "Имя", "type": "text", "required": True, "value": value("first_name")},
            {"name": "middle_name", "label": "Отчество", "type": "text", "value": value("middle_name") or ""},
            {
                "name": "position_type_id",
                "label": "Тип должности",
                "type": "select",
                "required": True,
                "options": _select_options(positions, value("position_type_id", None)),
            },
            {
                "name": "status_id",
                "label": "Статус",
                "type": "select",
                "required": True,
                "options": _select_options(statuses, value("status_id", None)),
            },
            {
                "name": "subordinates_total",
                "label": "Всего подчинённых",
                "type": "number",
                "value": value("subordinates_total", 0) or 0,
            },
            {
                "name": "subordinates_available",
                "label": "Доступно подчинённых",
                "type": "number",
                "value": value("subordinates_available", 0) or 0,
            },
            {
                "name": "is_stackholder",
                "label": "Является стейкхолдером (разработчик)",
                "type": "checkbox",
                "checked": bool(value("is_stackholder", 0)),
            },
        ]
    )
    return fields


def detail_info(employee: dict[str, Any], load: float) -> list[tuple[str, str]]:
    full_name = " ".join(
        part for part in (employee.get("last_name"), employee.get("first_name"), employee.get("middle_name")) if part
    )
    return [
        ("Сотрудник", html.escape(full_name)),
        ("Должность", html.escape(str(employee.get("position_name") or "—"))),
        ("Статус", _status_badge(employee.get("status_name"), employee.get("is_available"))),
        (
            "Роль",
            html.escape(role_label(employee.get("user_role"), bool(employee.get("user_analyst"))))
            if employee.get("user_role")
            else "—",
        ),
        ("Логин", html.escape(str(employee.get("user_login"))) if employee.get("user_login") else "—"),
        (
            "Подчинённые",
            f"{employee.get('subordinates_total') or 0} (доступно: {employee.get('subordinates_available') or 0})",
        ),
        ("Загрузка", f"{round(load * 100)}%"),
    ]


def tasks_table(request: Request, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        [
            _link(request, "task_detail", f"#{task['id']}", id=task["id"]),
            html.escape(str(task.get("pname") or "-")),
            html.escape(str(task.get("stype") or "-")),
            html.escape(str(task.get("description") or "")[:50]),
            html.escape(str(task.get("prio") or "")),
            html.escape(str(task.get("deadline") or "-")),
            _status_badge(task.get("st"), task.get("color")),
            f"{round(float(task['share']) * 100)}%",
        ]
        for task in tasks
    ]
    return {
        "title": "Задачи, где сотрудник назначен",
        "headers": ["ID", "Проект", "Этап", "Задача", "Приоритет", "Срок", "Статус", "Доля"],
        "rows": rows,
    }


def subtasks_table(request: Request, subtasks: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        [
            _link(request, "subtask_detail", f"#{row['id']}", id=row["id"]),
            html.escape(str(row.get("parent") or "")[:50]),
            html.escape(str(row.get("description") or "")[:50]),
            html.escape(str(row.get("prio") or "")),
            html.escape(str(row.get("deadline") or "-")),
            _status_badge(row.get("st"), row.get("color")),
            f"{round(float(row['share']) * 100)}%",
        ]
        for row in subtasks
    ]
    return {
        "title": "Подзадачи, где сотрудник назначен",
        "headers": ["ID", "Родительская задача", "Описание", "Приоритет", "Срок", "Статус", "Доля"],
        "rows": rows,
    }
