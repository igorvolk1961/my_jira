"""HTML-представление страницы управления базой данных."""

import html
from typing import Any

from fastapi import Request

Row = dict[str, Any]


def _url(request: Request, endpoint: str, fallback: str, **params: Any) -> str:
    try:
        return str(request.url_for(endpoint, **params))
    except Exception:
        return fallback


def _esc(value: Any) -> str:
    return html.escape(str(value))


def content(request: Request, *, current: str, files: list[Row], admin: bool, preselect: str) -> str:
    rows = ""
    for item in files:
        name = str(item["name"])
        active = '<span class="badge" style="background:#27ae60">активная</span>' if name == current else ""
        use_link = (
            ""
            if name == current
            else f'<a href="{_url(request, "database_use", f"/database/use/{name}", name=name)}"'
            ' class="btn btn-primary">Использовать</a> '
        )
        copy_link = (
            f'<a href="{_url(request, "database_index", f"/database?copy={name}", copy=name)}"'
            ' class="btn btn-warning">Копировать</a> '
            if admin
            else ""
        )
        delete_link = (
            f'<a href="{_url(request, "database_delete", f"/database/delete/{name}", name=name)}"'
            ' class="btn btn-danger" onclick="return confirm(\'Удалить БД?\')">Удалить</a>'
        )
        rows += f"""
        <tr>
            <td>{_esc(name)} {active}</td>
            <td>{int(item["size"]):,} байт</td>
            <td>
                {use_link}
                {copy_link}
                {delete_link}
            </td>
        </tr>"""

    source_options = "".join(
        f'<option value="{_esc(item["name"])}" {"selected" if item["name"] == preselect else ""}>'
        f"{_esc(item['name'])}</option>"
        for item in files
    )

    copy_card = ""
    if admin:
        copy_card = f"""
    <div class="card">
        <h2>Скопировать БД</h2>
        <p class="muted" style="margin-top:6px;">
            Копия файла базы данных — удобно для отдельной БД на урок (каждый урок или два).
            Копия создаётся без изменений; при необходимости данные удаляются вручную.
        </p>
        <form method="POST" action="{_url(request, "database_copy", "/database/copy")}">
            <div class="form-group">
                <label>Исходная БД</label>
                <select name="source" required>{source_options}</select>
            </div>
            <div class="form-group">
                <label>Имя копии</label>
                <input type="text" name="name" placeholder="например, urok_2" required>
            </div>
            <div class="form-group">
                <label style="font-weight:normal;">
                    <input type="checkbox" name="switch" value="1" checked style="width:auto; display:inline; margin-right:6px;">
                    Переключиться на копию
                </label>
            </div>
            <button type="submit" class="btn btn-success">Создать копию</button>
        </form>
    </div>"""

    return f"""
    <div class="card">
        <h2>Управление базой данных</h2>
        <p style="margin-top:10px;">Текущая активная БД: <strong>{_esc(current)}</strong></p>
    </div>
    <div class="card">
        <h2>Создать новую БД</h2>
        <form method="POST" action="{_url(request, "database_create", "/database/create")}">
            <div class="form-group">
                <label>Имя новой БД</label>
                <input type="text" name="name" placeholder="например, projekt_alpha" required>
            </div>
            <button type="submit" class="btn btn-success">Создать и переключиться</button>
        </form>
    </div>
    {copy_card}
    <div class="card">
        <h2>Имеющиеся БД</h2>
        <table>
            <thead><tr><th>Имя</th><th>Размер</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """
