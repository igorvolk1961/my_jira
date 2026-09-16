"""HTML-представление домена «Проекты» (карточка, вкладки, дерево этапов)."""

import html
from datetime import date
from typing import Any

from fastapi import Request

Row = dict[str, Any]

_PRIORITY_COLORS = ["#95a5a6", "#3498db", "#f39c12", "#e67e22", "#e74c3c"]


def _url(request: Request, name: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return "#"


def _esc(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def projects_table(request: Request, projects: list[Row]) -> dict[str, Any]:
    headers = [
        "ID",
        "Название",
        "Главный стейкхолдер",
        "Стоимость",
        "MVP срок",
        "Проект срок",
        "Приоритет",
        "Действия",
    ]
    rows: list[list[str]] = []
    for p in projects:
        pid = int(p["id"])
        if p["main_stakeholder_id"]:
            stakeholder = (
                f'<a href="{_url(request, "stakeholder_detail", id=p["main_stakeholder_id"])}">'
                f"{_esc(p['last_name'])} {_esc(p['first_name'])}</a>"
            )
        else:
            stakeholder = "-"
        weight = int(p["weight"] or 1)
        color = _PRIORITY_COLORS[weight - 1] if 1 <= weight <= len(_PRIORITY_COLORS) else _PRIORITY_COLORS[0]
        actions = (
            f'<a href="{_url(request, "project_detail", id=pid)}" class="btn btn-success">Открыть</a> '
            f'<a href="{_url(request, "project_edit", id=pid)}" class="btn btn-primary">Изменить</a> '
            f'<a href="{_url(request, "project_delete", id=pid)}" class="btn btn-danger"'
            f" onclick=\"return confirm('Удалить?')\">Удалить</a>"
        )
        rows.append(
            [
                str(pid),
                f'<a href="{_url(request, "project_detail", id=pid)}">{_esc(p["name"])}</a>',
                stakeholder,
                _esc(p["cost"]) if p["cost"] is not None else "-",
                _esc(p["mvp_deadline"]) if p["mvp_deadline"] else "-",
                _esc(p["deadline"]) if p["deadline"] else "-",
                f'<span class="badge" style="background: {color}">{_esc(p["priority_name"])}</span>',
                actions,
            ]
        )
    return {"title": "Проекты", "headers": headers, "rows": rows}


def _select_options(
    items: list[Row],
    label: Any,
    selected: Any = None,
    empty_label: str | None = None,
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if empty_label is not None:
        options.append({"value": "", "label": empty_label, "selected": selected in (None, "", 0)})
    for item in items:
        options.append(
            {
                "value": item["id"],
                "label": label(item),
                "selected": selected is not None and str(item["id"]) == str(selected),
            }
        )
    return options


def project_form_fields(options: dict[str, list[Row]], project: Row | None = None) -> list[dict[str, Any]]:
    current = project or {}
    stakeholders = options.get("stakeholders", [])
    priorities = options.get("priorities", [])
    return [
        {
            "name": "name",
            "label": "Название",
            "type": "text",
            "required": True,
            "value": current.get("name") or "",
        },
        {
            "name": "description",
            "label": "Описание",
            "type": "textarea",
            "value": current.get("description") or "",
        },
        {
            "name": "main_stakeholder_id",
            "label": "Главный стейкхолдер",
            "type": "select",
            "options": _select_options(
                stakeholders,
                lambda s: f"{s['last_name']} {s['first_name']}",
                current.get("main_stakeholder_id"),
                "Не выбран",
            ),
        },
        {
            "name": "cost",
            "label": "Стоимость",
            "type": "number",
            "value": current.get("cost") if current.get("cost") is not None else "",
        },
        {
            "name": "mvp_deadline",
            "label": "Срок MVP",
            "type": "date",
            "value": current.get("mvp_deadline") or "",
        },
        {
            "name": "deadline",
            "label": "Срок проекта",
            "type": "date",
            "value": current.get("deadline") or "",
        },
        {
            "name": "priority_id",
            "label": "Приоритет",
            "type": "select",
            "required": True,
            "options": _select_options(priorities, lambda p: p["name"], current.get("priority_id")),
        },
    ]


def requirements_block(request: Request, requirements: list[Row], project_id: int) -> tuple[str, int]:
    rows = "".join(
        [
            "<tr>"
            f"<td>{r['id']}</td>"
            f"<td>{_esc(r['type_name'])}</td>"
            f"<td>{_stakeholder_cell(request, r)}</td>"
            f"<td>{_esc(r['description'][:80])}</td>"
            f"<td>{_esc(r['priority_name'])}</td>"
            "<td>"
            f'<a href="{_url(request, "requirement_detail", id=r["id"])}" class="btn btn-success">Открыть</a> '
            f'<a href="{_url(request, "requirement_edit", id=r["id"])}" class="btn btn-primary">Изменить</a> '
            f'<a href="{_url(request, "requirement_delete", id=r["id"])}" class="btn btn-danger"'
            f" onclick=\"return confirm('Удалить?')\">Удалить</a>"
            "</td>"
            "</tr>"
            for r in requirements
        ]
    )
    add_link = _url(request, "requirement_create", project_id=project_id)
    html_out = f"""
        <a href="{add_link}" class="btn btn-success">+ Добавить требование</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Тип</th><th>Стейкхолдер</th><th>Описание</th><th>Приоритет</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>"""
    return html_out, len(requirements)


def _stakeholder_cell(request: Request, row: Row) -> str:
    if not row.get("stakeholder_id"):
        return "-"
    return (
        f'<a href="{_url(request, "stakeholder_detail", id=row["stakeholder_id"])}">'
        f"{_esc(row.get('last_name') or '')} {_esc(row.get('first_name') or '')}</a>"
    )


def stakeholders_block(request: Request, data: dict[str, Any], project_id: int) -> tuple[str, int]:
    project_stakeholders = data["rows"]
    candidates = data["candidates"]
    assoc_ids: set[int] = data["assoc_ids"]
    main_id = data["main_id"]

    def quadrant(influence: int, interest: int) -> str:
        if influence >= 4 and interest >= 4:
            return "Ключевые игроки"
        if influence >= 4:
            return "Удовлетворять"
        if interest >= 4:
            return "Держать в курсе"
        return "Наблюдать"

    def remove_btn(stakeholder_id: int) -> str:
        if stakeholder_id in assoc_ids and stakeholder_id != main_id:
            return (
                f' <a href="{_url(request, "project_remove_stakeholder", id=project_id, stakeholder_id=stakeholder_id)}"'
                f' class="btn btn-danger" onclick="return confirm(\'Убрать?\')">Убрать</a>'
            )
        return ""

    stk_rows = "".join(
        [
            f"""
        <tr>
            <td class="name-cell"><a href="{_url(request, "stakeholder_detail", id=s["id"])}">{_esc(s["last_name"])} {_esc(s["first_name"])}</a>"""
            + (' <span class="badge" style="background:#e74c3c">главный</span>' if s["id"] == main_id else "")
            + (
                ' <span class="badge" style="background:#3498db">добавлен</span>'
                if s["id"] in assoc_ids and s["id"] != main_id
                else ""
            )
            + f"""</td>
            <td>{_esc(s["type_name"])}</td>
            <td>{s["inf"]}/5, {s["ints"]}/5</td>
            <td>{quadrant(int(s["inf"]), int(s["ints"]))}</td>
            <td>{_esc(s["position"]) if s["position"] else "-"}</td>
            <td>{s["req_count"]}</td>
            <td><a href="{_url(request, "stakeholder_detail", id=s["id"])}" class="btn btn-success">Открыть</a>
                <a href="{_url(request, "stakeholder_edit", id=s["id"], origin=project_id)}" class="btn btn-primary">Изменить</a>{remove_btn(int(s["id"]))}</td>
        </tr>"""
            for s in project_stakeholders
        ]
    )
    candidate_options = "".join(
        f'<option value="{s["id"]}">{_esc(s["last_name"])} {_esc(s["first_name"])} — {_esc(s["type_name"])}</option>'
        for s in candidates
    )
    html_out = f"""
            <a href="{_url(request, "stakeholder_create", project_id=project_id)}" class="btn btn-success">+ Добавить стейкхолдера</a>
            <form method="POST" action="{_url(request, "project_add_stakeholder", id=project_id)}" style="display:inline-flex; gap:6px; margin-left:8px; vertical-align:middle;">
                <select name="stakeholder_id" required>
                    <option value="">— выберите из имеющихся —</option>
                    {candidate_options}
                </select>
                <button type="submit" class="btn btn-primary">Добавить</button>
            </form>
            <table>
                <thead>
                    <tr><th>Стейкхолдер</th><th>Тип</th><th>Влияние/Интерес</th><th>Квадрант</th><th>Должность</th><th>Требований</th><th>Действия</th></tr>
                </thead>
                <tbody>{stk_rows}</tbody>
            </table>"""
    return html_out, len(project_stakeholders)


def _assignees_html(request: Request, lines: list[Row]) -> str:
    if not lines:
        return '<span class="muted">исполнители не назначены</span>'
    items = [
        f'<a href="{_url(request, "employee_detail", id=a["eid"])}">{_esc(a["last_name"])} {_esc(a["first_name"])}</a>'
        f" ({int(a['share'] * 100)}%, назначил: {_esc(a['assigner'] or '—')})"
        for a in lines
    ]
    return "Исполнители: " + ", ".join(items)


def _assignments_block(request: Request, lines: list[Row]) -> str:
    return f'<div class="assign">{_assignees_html(request, lines)}</div>'


def _render_subtask(request: Request, subtask: Row, project_id: int) -> str:
    children = subtask.get("children", [])
    assign_url = _url(request, "task_assignment_create", task_id=subtask["id"], task_kind="subtask", origin=project_id)
    edit_link = _url(request, "subtask_edit", id=subtask["id"], origin=project_id)
    card_link = _url(request, "subtask_detail", id=subtask["id"])
    child_link = _url(request, "subtask_create", parent_subtask_id=subtask["id"], origin=project_id)
    del_link = _url(request, "subtask_delete", id=subtask["id"])
    overdue = (
        bool(subtask["deadline"])
        and str(subtask["deadline"]) < date.today().isoformat()
        and subtask["status_name"] not in ("Выполнена", "Отменена")
    )
    deadline_style = " color:#e74c3c; font-weight:bold;" if overdue else ""
    children_html = "".join(_render_subtask(request, c, project_id) for c in children)
    return f"""
            <details class="subtask" open>
                <summary>
                    <span class="node-info">
                        <a href="{card_link}">Подзадача #{subtask["id"]}</a>
                        <span class="badge" style="background: {subtask["status_color"] or "#95a5a6"}">{_esc(subtask["status_name"])}</span>
                        <span class="node-meta">Приоритет: {_esc(subtask["priority_name"])}</span>
                        <span class="node-meta" style="{deadline_style}">Срок: {subtask["deadline"] or "-"}</span>
                    </span>
                    <span class="node-actions">
                        <a class="btn btn-warning" href="{assign_url}">Назначить</a>
                        <a class="btn btn-primary" href="{edit_link}">Изменить</a>
                        <a class="btn btn-success" href="{child_link}">+ Подзадача</a>
                        <a class="btn btn-danger" href="{del_link}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">
                    {_assignments_block(request, subtask.get("assignments", []))}
                    {children_html}
                </div>
            </details>"""


def _render_task(request: Request, task: Row, project_id: int) -> str:
    subtasks_html = "".join(_render_subtask(request, s, project_id) for s in task.get("subtasks", []))
    assign_url = _url(request, "task_assignment_create", task_id=task["id"], task_kind="task", origin=project_id)
    subtask_link = _url(request, "subtask_create", parent_task_id=task["id"], origin=project_id)
    edit_link = _url(request, "task_edit", id=task["id"], origin=project_id)
    card_link = _url(request, "task_detail", id=task["id"])
    del_link = _url(request, "task_delete", id=task["id"])
    overdue = (
        bool(task["deadline"])
        and str(task["deadline"]) < date.today().isoformat()
        and task["status_name"] not in ("Выполнена", "Отменена")
    )
    deadline_style = " color:#e74c3c; font-weight:bold;" if overdue else ""
    return f"""
            <details class="task" open>
                <summary>
                    <span class="node-info">
                        <a href="{card_link}">Задача #{task["id"]}</a>
                        <span class="badge" style="background: {task["status_color"] or "#95a5a6"}">{_esc(task["status_name"])}</span>
                        <span class="node-meta">Тип: {_esc(task["type_name"]) if task["type_name"] else "-"}</span>
                        <span class="node-meta">Приоритет: {_esc(task["priority_name"])}</span>
                        <span class="node-meta" style="{deadline_style}">Срок: {task["deadline"] or "-"}</span>
                    </span>
                    <span class="node-actions">
                        <a class="btn btn-warning" href="{assign_url}">Назначить</a>
                        <a class="btn btn-primary" href="{edit_link}">Изменить</a>
                        <a class="btn btn-success" href="{subtask_link}">+ Подзадача</a>
                        <a class="btn btn-danger" href="{del_link}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">
                    {_assignments_block(request, task.get("assignments", []))}
                    {subtasks_html}
                </div>
            </details>"""


def stage_tree_block(request: Request, tree: dict[str, Any], project_id: int) -> tuple[str, int]:
    stage_html = ""
    for stage in tree["stages"]:
        stage_tasks = stage.get("tasks", [])
        inner = "".join(_render_task(request, t, project_id) for t in stage_tasks)
        if not stage_tasks:
            inner = '<div class="node-body muted">Задач по этапу нет</div>'
        stage_html += f"""
            <details class="stage" open>
                <summary>
                    <span class="node-info">
                        {_esc(stage["type_name"])}
                        <span class="badge" style="background: {stage["color"] or "#95a5a6"}">{_esc(stage["status_name"])}</span>
                        <span class="node-meta">План. окончание: {stage["planned_end"] or "-"}</span>
                    </span>
                    <span class="node-actions">
                        <a class="btn btn-success" href="{_url(request, "task_create", stage_id=stage["id"], origin=project_id)}">+ Задача</a>
                        <a class="btn btn-danger" href="{_url(request, "project_stage_delete", id=stage["id"])}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">{inner}</div>
            </details>"""
    html_out = f"""
            <a href="{_url(request, "project_stage_create")}" class="btn btn-success">+ Добавить этап</a>
            <div class="tree">{stage_html}</div>"""
    return html_out, int(tree["count"])


def employees_block(request: Request, data: dict[str, Any], project_id: int) -> tuple[str, int]:
    emp_rows = data["rows"]
    candidates = data["candidates"]

    def remove_btn(employee_id: int) -> str:
        return (
            f' <a href="{_url(request, "project_remove_employee", id=project_id, employee_id=employee_id)}"'
            f' class="btn btn-danger" onclick="return confirm(\'Убрать?\')">Убрать</a>'
        )

    emp_rows_html = "".join(
        [
            f"""
        <tr>
            <td class="name-cell"><a href="{_url(request, "employee_detail", id=e["id"])}">{_esc(e["last_name"])} {_esc(e["first_name"])} {_esc(e["middle_name"] or "")}</a></td>
            <td>{_esc(e["position_name"])}</td>
            <td><span class="badge" style="background: {"#27ae60" if e["is_available"] else "#e74c3c"}">{_esc(e["status_name"])}</span></td>
            <td>{e["subordinates_total"]}</td>
            <td>
                <a href="{_url(request, "employee_detail", id=e["id"])}" class="btn btn-success">Открыть</a>
                <a href="{_url(request, "employee_edit", id=e["id"], origin=project_id)}" class="btn btn-primary">Изменить</a>{remove_btn(int(e["id"]))}
            </td>
        </tr>"""
            for e in emp_rows
        ]
    )
    candidate_options = "".join(
        f'<option value="{e["id"]}">{_esc(e["last_name"])} {_esc(e["first_name"])} — {_esc(e["position_name"])}</option>'
        for e in candidates
    )
    html_out = f"""
            <a href="{_url(request, "employee_create", project_id=project_id)}" class="btn btn-success">+ Добавить исполнителя</a>
            <form method="POST" action="{_url(request, "project_add_employee", id=project_id)}" style="display:inline-flex; gap:6px; margin-left:8px; vertical-align:middle;">
                <select name="employee_id" required>
                    <option value="">— выберите из имеющихся —</option>
                    {candidate_options}
                </select>
                <button type="submit" class="btn btn-primary">Добавить</button>
            </form>
            <table>
                <thead>
                    <tr><th>Исполнитель</th><th>Должность</th><th>Статус</th><th>Подчинённые</th><th>Действия</th></tr>
                </thead>
                <tbody>{emp_rows_html}</tbody>
            </table>"""
    return html_out, len(emp_rows)


def detail_content(
    request: Request,
    project: Row,
    req_html: str,
    req_count: int,
    stages_html: str,
    stages_count: int,
    stk_html: str,
    stk_count: int,
    emp_html: str,
    emp_count: int,
    active_tab: str,
) -> str:
    if project["main_stakeholder_id"]:
        stakeholder = (
            f'<a href="{_url(request, "stakeholder_detail", id=project["main_stakeholder_id"])}">'
            f"{_esc(project['last_name'])} {_esc(project['first_name'])}</a>"
        )
    else:
        stakeholder = "-"
    keys = ("req", "stages", "stk", "emp")
    btn = {k: ("tab-btn active" if active_tab == k else "tab-btn") for k in keys}
    panel = {k: ("tab-content active" if active_tab == k else "tab-content") for k in keys}
    return f"""
    <div class="card">
        <h2>{_esc(project["name"])}
            <span class="node-meta">
                | Приоритет: {_esc(project["priority_name"])}
                | Стейкхолдер: {stakeholder}
                | Стоимость: {project["cost"] or "-"}
                | Срок: {project["deadline"] or "-"}
            </span>
        </h2>
        <div class="tabs">
            <button class="{btn["req"]}" id="btn-req" onclick="showTab('req')">Требования ({req_count})</button>
            <button class="{btn["stages"]}" id="btn-stages" onclick="showTab('stages')">Этапы ({stages_count})</button>
            <button class="{btn["stk"]}" id="btn-stk" onclick="showTab('stk')">Стейкхолдеры ({stk_count})</button>
            <button class="{btn["emp"]}" id="btn-emp" onclick="showTab('emp')">Исполнители ({emp_count})</button>
        </div>
        <div class="{panel["req"]}" id="tab-req">
            {req_html}
        </div>
        <div class="{panel["stages"]}" id="tab-stages">
            {stages_html}
        </div>
        <div class="{panel["stk"]}" id="tab-stk">
            {stk_html}
        </div>
        <div class="{panel["emp"]}" id="tab-emp">
            {emp_html}
        </div>
    </div>
    <script>
    function showTab(name) {{
        document.querySelectorAll('.tab-btn').forEach(function(el) {{ el.classList.remove('active'); }});
        document.querySelectorAll('.tab-content').forEach(function(el) {{ el.classList.remove('active'); }});
        document.getElementById('btn-' + name).classList.add('active');
        document.getElementById('tab-' + name).classList.add('active');
    }}
    </script>
    """
