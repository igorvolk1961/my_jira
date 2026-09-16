"""HTML-представление домена «Этапы проектов»."""

import html
from typing import Any

from fastapi import Request

Row = dict[str, Any]


def _url(request: Request, name: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return "#"


def _esc(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def stages_table(request: Request, stages: list[Row]) -> dict[str, Any]:
    headers = ["ID", "Проект", "Тип этапа", "Статус", "Плановая дата завершения", "Действия"]
    rows: list[list[str]] = []
    for s in stages:
        rows.append(
            [
                str(s["id"]),
                _esc(s["project_name"]),
                _esc(s["type_name"]),
                f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{_esc(s["status_name"])}</span>',
                s["planned_end"] or "-",
                f'<a href="{_url(request, "project_stage_detail", id=s["id"])}" class="btn btn-success">Открыть</a> '
                f'<a href="{_url(request, "project_stage_edit", id=s["id"])}" class="btn btn-primary">Изменить</a> '
                f'<a href="{_url(request, "project_stage_delete", id=s["id"])}" class="btn btn-danger"'
                f" onclick=\"return confirm('Удалить?')\">Удалить</a>",
            ]
        )
    return {"title": "Этапы проектов", "headers": headers, "rows": rows}


def _select_options(
    items: list[Row],
    label: Any,
    selected: Any = None,
) -> list[dict[str, Any]]:
    return [
        {
            "value": item["id"],
            "label": label(item),
            "selected": selected is not None and str(item["id"]) == str(selected),
        }
        for item in items
    ]


def stage_form_fields(options: dict[str, list[Row]], stage: Row | None = None) -> list[dict[str, Any]]:
    current = stage or {}
    return [
        {
            "name": "project_id",
            "label": "Проект",
            "type": "select",
            "required": True,
            "options": _select_options(options.get("projects", []), lambda p: p["name"], current.get("project_id")),
        },
        {
            "name": "stage_type_id",
            "label": "Тип этапа",
            "type": "select",
            "required": True,
            "options": _select_options(
                options.get("stage_types", []), lambda t: t["name"], current.get("stage_type_id")
            ),
        },
        {
            "name": "status_id",
            "label": "Статус",
            "type": "select",
            "required": True,
            "options": _select_options(
                options.get("stage_statuses", []), lambda s: s["name"], current.get("status_id")
            ),
        },
        {
            "name": "planned_end",
            "label": "Плановая дата завершения",
            "type": "date",
            "value": current.get("planned_end") or "",
        },
    ]


def stage_detail(request: Request, stage: Row, tasks: list[Row]) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    info: list[tuple[str, str]] = [
        ("Этап", _esc(stage["type_name"])),
        (
            "Проект",
            f'<a href="{_url(request, "project_detail", id=stage["project_id"])}">{_esc(stage["pname"])}</a>',
        ),
        (
            "Статус",
            f'<span class="badge" style="background: {stage["color"] or "#95a5a6"}">{_esc(stage["status_name"])}</span>',
        ),
        ("Плановая дата", stage["planned_end"] or "-"),
    ]
    rows = [
        [
            f'<a href="{_url(request, "task_detail", id=t["id"])}">#{t["id"]}</a>',
            _esc(t["description"][:60]),
            _esc(t["prio"]),
            t["deadline"] or "-",
            f'<span class="badge" style="background: {t["color"] or "#95a5a6"}">{_esc(t["st"])}</span>',
            _esc(t["executors"]) if t["executors"] else "не назначено",
        ]
        for t in tasks
    ]
    add_task = (
        f'<a href="{_url(request, "task_create", stage_id=stage["id"], origin=stage["project_id"])}"'
        f' class="btn btn-success">+ Задача</a>'
    )
    tables = [
        {
            "title": "Задачи этапа " + add_task,
            "headers": ["ID", "Описание", "Приоритет", "Срок", "Статус", "Исполнители"],
            "rows": rows,
        }
    ]
    return info, tables
