"""Построение HTML для страниц стейкхолдеров (без SQL и бизнес-логики)."""

import html
from typing import Any

from fastapi import Request


def _url(request: Request, name: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return "#"


def _anchor(request: Request, name: str, label: str, css: str, **params: Any) -> str:
    return f'<a href="{html.escape(_url(request, name, **params))}" class="{css}">{html.escape(label)}</a>'


def _link(request: Request, name: str, label: str, **params: Any) -> str:
    url = _url(request, name, **params)
    if url == "#":
        return html.escape(label)
    return f'<a href="{html.escape(url)}">{html.escape(label)}</a>'


def list_table(request: Request, stakeholders: list[dict[str, Any]], is_admin: bool) -> dict[str, Any]:
    rows: list[list[str]] = []
    for stakeholder in stakeholders:
        actions = [_anchor(request, "stakeholder_detail", "Открыть", "btn btn-success", id=stakeholder["id"])]
        if is_admin:
            actions.append(_anchor(request, "stakeholder_edit", "Изменить", "btn btn-primary", id=stakeholder["id"]))
            actions.append(_anchor(request, "stakeholder_delete", "Удалить", "btn btn-danger", id=stakeholder["id"]))
        rows.append(
            [
                str(stakeholder["id"]),
                html.escape(
                    f"{stakeholder['last_name']} {stakeholder['first_name']} "
                    f"{stakeholder.get('middle_name') or ''}".strip()
                ),
                html.escape(str(stakeholder.get("type_name") or "")),
                html.escape(str(stakeholder.get("position") or "-")),
                str(stakeholder.get("priority") or ""),
                " ".join(actions),
            ]
        )
    return {
        "title": "Стейкхолдеры",
        "headers": ["ID", "ФИО", "Тип", "Должность", "Приоритет", "Действия"],
        "rows": rows,
    }


def detail_info(stakeholder: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        ("Стейкхолдер", html.escape(f"{stakeholder['last_name']} {stakeholder['first_name']}")),
        ("Тип", html.escape(str(stakeholder.get("type_name") or ""))),
        (
            "Влияние / Интерес",
            f"{stakeholder.get('inf')}/5, {stakeholder.get('ints')}/5",
        ),
        ("Должность", html.escape(str(stakeholder.get("position") or "-"))),
        ("Приоритет", str(stakeholder.get("priority") or "")),
    ]


def projects_table(request: Request, projects: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        [
            _link(request, "project_detail", str(project["name"]), id=project["id"]),
            html.escape(str(project.get("prio") or "")),
            html.escape(str(project.get("deadline") or "-")),
        ]
        for project in projects
    ]
    return {
        "title": "Проекты (главный стейкхолдер)",
        "headers": ["Проект", "Приоритет", "Срок"],
        "rows": rows,
    }


def requirements_table(request: Request, requirements: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        [
            _link(request, "requirement_detail", f"#{row['id']}", id=row["id"]),
            html.escape(str(row.get("description") or "")[:60]),
            html.escape(str(row.get("pname") or "")),
            html.escape(str(row.get("type_name") or "")),
            html.escape(str(row.get("prio") or "")),
        ]
        for row in requirements
    ]
    return {
        "title": "Требования стейкхолдера",
        "headers": ["ID", "Описание", "Проект", "Тип", "Приоритет"],
        "rows": rows,
    }


def interviews_table(request: Request, interviews: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        [
            _link(request, "interview_detail", f"#{row['id']}", id=row["id"]),
            html.escape(str(row.get("scheduled_at") or "-")),
        ]
        for row in interviews
    ]
    return {
        "title": "Интервью стейкхолдера",
        "headers": ["ID", "Дата-время"],
        "rows": rows,
    }
