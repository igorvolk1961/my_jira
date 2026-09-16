"""Построение данных для шаблонов (без SQL и бизнес-логики)."""

import html
from typing import Any

from fastapi import Request

from app.services.reference_service import Resource


def _label(resource: Resource, column: str) -> str:
    if column == "id":
        return "ID"
    for field in resource.fields:
        if field.name == column:
            return field.label
    return column


def _cell(resource: Resource, item: Any, column: str) -> str:
    value = getattr(item, column, None)
    field = next((f for f in resource.fields if f.name == column), None)
    if field is not None and field.type == "checkbox":
        return "Да" if value else "Нет"
    if value is None or value == "":
        return "-"
    return html.escape(str(value))


def reference_table(request: Request, resource: Resource, items: list[Any], can_edit: bool = True) -> dict[str, Any]:
    headers = [_label(resource, column) for column in resource.columns]
    if can_edit:
        headers.append("Действия")
    rows: list[list[str]] = []
    for item in items:
        cells = [_cell(resource, item, column) for column in resource.columns]
        if can_edit:
            edit_url = request.url_for(resource.edit_name, id=item.id)
            delete_url = request.url_for(resource.delete_name, id=item.id)
            cells.append(
                f'<a href="{edit_url}" class="btn btn-primary">Изменить</a> '
                f'<a href="{delete_url}" class="btn btn-danger" onclick="return confirm(\'Удалить?\')">Удалить</a>'
            )
        rows.append(cells)
    return {"title": resource.title, "headers": headers, "rows": rows}


def reference_form_fields(resource: Resource, item: Any = None) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for field in resource.fields:
        value = getattr(item, field.name, None) if item is not None else None
        spec: dict[str, Any] = {
            "name": field.name,
            "label": field.label,
            "type": field.type if field.type != "number" else "number",
            "required": field.required,
            "value": value if value is not None else "",
        }
        if field.type == "checkbox":
            spec["checked"] = bool(value)
        fields.append(spec)
    return fields
