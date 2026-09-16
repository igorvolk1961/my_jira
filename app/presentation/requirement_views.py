"""HTML-представление домена «Требования»."""

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


def requirements_table(request: Request, requirements: list[Row]) -> dict[str, Any]:
    headers = ["ID", "Проект", "Стейкхолдер", "Тип", "Описание", "Приоритет", "Действия"]
    rows: list[list[str]] = []
    for r in requirements:
        if r["stakeholder_id"]:
            stakeholder = (
                f'<a href="{_url(request, "stakeholder_detail", id=r["stakeholder_id"])}">'
                f"{_esc(r['last_name'])} {_esc(r['first_name'])}</a>"
            )
        else:
            stakeholder = "-"
        rows.append(
            [
                str(r["id"]),
                f'<a href="{_url(request, "project_detail", id=r["project_id"])}">{_esc(r["project_name"])}</a>',
                stakeholder,
                _esc(r["type_name"]),
                f"{_esc(r['description'][:50])}...",
                _esc(r["priority_name"]),
                f'<a href="{_url(request, "requirement_detail", id=r["id"])}" class="btn btn-success">Открыть</a> '
                f'<a href="{_url(request, "requirement_edit", id=r["id"])}" class="btn btn-primary">Изменить</a> '
                f'<a href="{_url(request, "requirement_delete", id=r["id"])}" class="btn btn-danger"'
                f" onclick=\"return confirm('Удалить?')\">Удалить</a>",
            ]
        )
    return {"title": "Требования", "headers": headers, "rows": rows}


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


def requirement_form_fields(
    options: dict[str, list[Row]],
    requirement: Row | None = None,
    prefill: dict[str, Any] | None = None,
    next_url: str | None = None,
    task_id: Any = None,
) -> list[dict[str, Any]]:
    current = requirement or {}
    fill = prefill or {}
    project_selected = current.get("project_id", fill.get("project_id"))
    type_selected = current.get("requirement_type_id", fill.get("requirement_type_id"))
    nfr_selected = current.get("nfr_type_id", fill.get("nfr_type_id"))
    return [
        {"name": "task_id", "label": "", "type": "hidden", "value": task_id or ""},
        {"name": "next", "label": "", "type": "hidden", "value": next_url or ""},
        {
            "name": "project_id",
            "label": "Проект",
            "type": "select",
            "required": True,
            "options": _select_options(options.get("projects", []), lambda p: p["name"], project_selected),
        },
        {
            "name": "stakeholder_id",
            "label": "Стейкхолдер",
            "type": "select",
            "options": _select_options(
                options.get("stakeholders", []),
                lambda s: f"{s['last_name']} {s['first_name']}",
                current.get("stakeholder_id"),
                "Не выбран",
            ),
        },
        {
            "name": "requirement_type_id",
            "label": "Тип требования",
            "type": "select",
            "required": True,
            "options": _select_options(options.get("requirement_types", []), lambda t: t["name"], type_selected),
        },
        {
            "name": "nfr_type_id",
            "label": "Тип нефункционального требования",
            "type": "select",
            "options": _select_options(
                options.get("nfr_types", []), lambda t: t["name"], nfr_selected, "— не выбрано —"
            ),
        },
        {
            "name": "description",
            "label": "Описание",
            "type": "textarea",
            "required": True,
            "value": current.get("description") or "",
        },
        {
            "name": "priority_id",
            "label": "Приоритет",
            "type": "select",
            "required": True,
            "options": _select_options(options.get("priorities", []), lambda p: p["name"], current.get("priority_id")),
        },
        {
            "name": "acceptance_criteria",
            "label": "Критерий проверки",
            "type": "textarea",
            "value": current.get("acceptance_criteria") or "",
        },
    ]


def requirement_detail(
    request: Request, requirement: Row, tasks: list[Row]
) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    info: list[tuple[str, str]] = [
        ("Требование", f"#{requirement['id']}"),
        ("Проект", _esc(requirement["pname"])),
        ("Тип", _esc(requirement["type_name"])),
        (
            "Тип нефункционального требования",
            _esc(requirement["nfr_type_name"]) if requirement["nfr_type_name"] else "-",
        ),
        ("Приоритет", _esc(requirement["prio"])),
        (
            "Стейкхолдер",
            f"{_esc(requirement['last_name']) if requirement['last_name'] else '-'} {_esc(requirement['first_name'] or '')}",
        ),
        ("Описание", _esc(requirement["description"])),
        ("Критерий проверки", _esc(requirement["acceptance_criteria"]) or "-"),
    ]
    rows = [
        [
            f'<a href="{_url(request, "task_detail", id=t["id"])}">#{t["id"]}</a>',
            t["description"][:60],
            _esc(t["stype"]) if t["stype"] else "-",
            _esc(t["prio"]),
            t["deadline"] or "-",
            f'<span class="badge" style="background: {t["color"] or "#95a5a6"}">{_esc(t["st"])}</span>',
        ]
        for t in tasks
    ]
    tables = [
        {
            "title": "Задачи, реализующие требование",
            "headers": ["ID", "Описание", "Этап", "Приоритет", "Срок", "Статус"],
            "rows": rows,
        }
    ]
    return info, tables
