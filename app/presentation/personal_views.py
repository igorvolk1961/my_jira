"""Построение HTML для «Мои задачи» и админ-вкладок задач (без SQL)."""

import html
from datetime import date
from typing import Any

from fastapi import Request

from app.presentation.task_views import status_form_html
from app.presentation.urls import url_or

_DONE_STATUSES = ("Выполнена", "Отменена")


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _text(value: Any, dash: str = "—") -> str:
    if value is None or value == "":
        return dash
    return _esc(value)


def _item_row(
    request: Request, item: dict[str, Any], statuses: list[dict[str, Any]], extra_action: str | None, back: str
) -> str:
    is_task = item["kind"] == "task"
    link_endpoint = "task_detail" if is_task else "subtask_detail"
    kind_label = "Задача" if is_task else "Подзадача"
    deadline = item["deadline"] or "-"
    overdue = False
    if item["deadline"]:
        overdue = str(item["deadline"]) < date.today().isoformat() and item["status_name"] not in _DONE_STATUSES
    deadline_style = ' style="color:#e74c3c; font-weight:bold;"' if overdue else ""
    if extra_action is not None:
        action = extra_action
    else:
        endpoint = "task_status_change" if is_task else "subtask_status_change"
        action = status_form_html(request, endpoint, item["id"], statuses, item["status_id"], back=back)
    return (
        "<tr>"
        f"<td>{kind_label}</td>"
        f'<td><a href="{url_or(request, link_endpoint, "#", id=item["id"])}">#{item["id"]}</a> '
        f"{_esc((item['description'] or '')[:50])}</td>"
        f"<td>{_text(item['project_name'])}</td>"
        f"<td>{_text(item['executors'])}</td>"
        f"<td>{_text(item['assigner'])}</td>"
        f"<td{deadline_style}>{_esc(deadline)}</td>"
        f'<td><span class="badge" style="background: {item["status_color"] or "#95a5a6"}">'
        f"{_esc(item['status_name'])}</span></td>"
        f"<td>{action}</td>"
        "</tr>"
    )


def _render_rows(
    request: Request,
    items: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    back: str,
    extra_action: Any = None,
) -> str:
    body = "".join(
        _item_row(request, item, statuses, extra_action(item) if extra_action else None, back) for item in items
    )
    if not body:
        body = '<tr><td colspan="8" class="muted">Записей нет</td></tr>'
    return body


def my_tasks_content(
    request: Request,
    items: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
) -> str:
    groups: dict[tuple[Any, str], list[dict[str, Any]]] = {}
    for item in items:
        key = (item["project_id"], item["project_name"] or "Без проекта")
        groups.setdefault(key, []).append(item)
    back = url_or(request, "my_tasks", "#")
    blocks = ""
    for (project_id, project_name), rows in sorted(groups.items(), key=lambda kv: str(kv[0][1])):
        body = _render_rows(request, rows, statuses, back)
        if project_id:
            title = f'<a href="{url_or(request, "project_detail", "#", id=project_id)}">{_esc(project_name)}</a>'
        else:
            title = _esc(project_name)
        blocks += (
            '<div class="card">'
            f"<h2>{title}</h2>"
            "<table><thead><tr><th>Тип</th><th>Объект</th><th>Проект</th><th>Исполнители</th>"
            "<th>Назначил</th><th>Срок</th><th>Статус</th><th>Изменить статус</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div>"
        )
    if not blocks:
        blocks = '<div class="card"><p class="muted">Назначенных задач нет</p></div>'
    return blocks


def _project_employee_options(employees: list[dict[str, Any]]) -> str:
    options = ""
    for employee in employees:
        load = int(float(employee["load"]) * 100)
        options += (
            f'<option value="{employee["id"]}">{_esc(employee["last_name"])} {_esc(employee["first_name"])}'
            f" — {_esc(employee['pos'])} (загрузка {load}%)</option>"
        )
    return options


def admin_tasks_content(
    request: Request,
    items: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    tab: str,
    project_employees: dict[int, list[dict[str, Any]]],
) -> str:
    create_url = url_or(request, "task_assignment_create", "#")

    def assign_form(item: dict[str, Any]) -> str:
        project_id = item["project_id"]
        employees = project_employees.get(project_id) if project_id else None
        if not employees:
            return '<span class="muted">нет команды проекта</span>'
        default_share = "1.0" if item["kind"] == "subtask" else "0.5"
        next_url = url_or(request, "admin_tasks", "#", tab=tab)
        return (
            f'<form method="POST" action="{create_url}" style="display:flex; gap:6px; align-items:center;'
            ' margin:0; flex-wrap:wrap;">'
            f'<input type="hidden" name="task_kind" value="{item["kind"]}">'
            f'<input type="hidden" name="task_id" value="{item["id"]}">'
            f'<input type="hidden" name="next" value="{next_url}">'
            f'<select name="employee_id" required>{_project_employee_options(employees)}</select>'
            f'<input type="number" name="share" step="0.1" min="0" max="1" value="{default_share}"'
            ' style="width:80px;" required>'
            '<button type="submit" class="btn btn-warning" style="margin:0;">Назначить</button></form>'
        )

    back = url_or(request, "admin_tasks", "#", tab=tab)
    body = _render_rows(request, items, statuses, back, extra_action=assign_form if tab == "unassigned" else None)

    def tab_link(key: str, label: str) -> str:
        active = "btn-success" if tab == key else "btn-primary"
        return f'<a href="{url_or(request, "admin_tasks", "#", tab=key)}" class="btn {active}">{label}</a>'

    return (
        '<div class="card">'
        "<h2>Задачи</h2>"
        '<div style="margin-bottom:12px;">'
        f"{tab_link('unassigned', 'Не назначенные')} "
        f"{tab_link('not_accepted', 'Не принятые к исполнению')} "
        f"{tab_link('overdue', 'Просроченные')}"
        "</div>"
        "<table><thead><tr><th>Тип</th><th>Объект</th><th>Проект</th><th>Исполнители</th>"
        "<th>Назначил</th><th>Срок</th><th>Статус</th><th>Действия</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )
