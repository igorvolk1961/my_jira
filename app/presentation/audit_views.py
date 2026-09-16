"""HTML-представление журнала аудита."""

import html
from typing import Any
from urllib.parse import urlencode

from fastapi import Request

Row = dict[str, Any]


def _url(request: Request, **params: Any) -> str:
    clean = {key: value for key, value in params.items() if value is not None}
    try:
        return str(request.url_for("audit_index", **clean))
    except Exception:
        query = urlencode(clean)
        return "/audit" + (f"?{query}" if query else "")


def _options(items: list[Row], selected: str) -> str:
    out = '<option value="">— все —</option>'
    for item in items:
        out += (
            f'<option value="{item["id"]}"'
            f" {'selected' if str(item['id']) == str(selected) else ''}>"
            f"{html.escape(str(item['name']))}</option>"
        )
    return out


def _sort_link(request: Request, label: str, key: str, data: Row) -> str:
    current_sort = str(data["sort"])
    order_dir = str(data["order_dir"])
    next_dir = "asc" if (current_sort == key and order_dir == "DESC") else "desc"
    href = _url(
        request,
        project_id=data["project_id"],
        position_id=data["position_id"],
        user_id=data["user_id"],
        sort=key,
        dir=next_dir,
    )
    return f'<a href="{href}">{label}</a>'


def content(request: Request, data: Row) -> str:
    rows_html = "".join(
        f"""
        <tr>
            <td>{html.escape(str(row["created_at"]))}</td>
            <td>{html.escape(str(row["user_name"]))}</td>
            <td>{html.escape(str(row["action"]))}</td>
            <td>{html.escape(str(row["entity_type"] or ""))} {("#" + str(row["entity_id"])) if row["entity_id"] else ""}</td>
            <td>{html.escape(str(row["project_name"] or "—"))}</td>
            <td>{html.escape(str(row["position_name"] or "—"))}</td>
            <td>{html.escape(str(row["details"] or ""))}</td>
        </tr>"""
        for row in data["rows"]
    )
    if not rows_html:
        rows_html = '<tr><td colspan="7" class="muted">Записей нет</td></tr>'

    project_opts = _options(data["projects"], str(data["project_id"]))
    position_opts = _options(data["positions"], str(data["position_id"]))
    user_opts = _options(data["users"], str(data["user_id"]))
    reset_url = _url(request)

    return f"""
    <div class="card">
        <h2>Аудит действий</h2>
        <form method="GET" style="margin-top:10px;">
            <div class="form-group">
                <label>Проект</label>
                <select name="project_id">{project_opts}</select>
            </div>
            <div class="form-group">
                <label>Должность</label>
                <select name="position_id">{position_opts}</select>
            </div>
            <div class="form-group">
                <label>Пользователь</label>
                <select name="user_id">{user_opts}</select>
            </div>
            <button type="submit" class="btn btn-primary">Применить</button>
            <a href="{reset_url}" class="btn btn-warning">Сбросить</a>
        </form>
    </div>
    <div class="card">
        <table>
            <thead><tr>
                <th>{_sort_link(request, "Дата", "created_at", data)}</th>
                <th>{_sort_link(request, "Пользователь", "user", data)}</th>
                <th>{_sort_link(request, "Действие", "action", data)}</th>
                <th>Объект</th>
                <th>{_sort_link(request, "Проект", "project", data)}</th>
                <th>Должность</th>
                <th>Детали</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """
