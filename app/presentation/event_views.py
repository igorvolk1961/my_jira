"""Построение HTML для страниц событий (без SQL и бизнес-логики)."""

import html
from datetime import datetime
from typing import Any

from fastapi import Request


def _url(request: Request, name: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return "#"


def _anchor(request: Request, name: str, label: str, css: str, **params: Any) -> str:
    return f'<a href="{html.escape(_url(request, name, **params))}" class="{css}">{html.escape(label)}</a>'


def list_table(request: Request, events: list[dict[str, Any]], is_admin: bool) -> dict[str, Any]:
    rows: list[list[str]] = []
    for event in events:
        actions = [_anchor(request, "event_detail", "Открыть", "btn btn-success", id=event["id"])]
        if is_admin:
            actions.append(_anchor(request, "event_edit", "Изменить", "btn btn-primary", id=event["id"]))
            actions.append(_anchor(request, "event_delete", "Удалить", "btn btn-danger", id=event["id"]))
        description = str(event.get("description") or "")
        decision = str(event.get("decision") or "-")
        rows.append(
            [
                str(event["id"]),
                html.escape(str(event.get("occurred_at") or "")),
                html.escape(description[:60]) + "...",
                html.escape(decision[:60]),
                " ".join(actions),
            ]
        )
    return {
        "title": "События (вводные преподавателя)",
        "headers": ["ID", "Дата/время", "Описание", "Решение", "Действия"],
        "rows": rows,
    }


def detail_info(event: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        ("Событие", f"#{event['id']}"),
        ("Дата", html.escape(str(event.get("occurred_at") or "-"))),
        ("Описание", html.escape(str(event.get("description") or ""))),
        ("Решение", html.escape(str(event.get("decision") or "-"))),
    ]


def form_fields(event: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    occurred = ""
    if event and event.get("occurred_at"):
        occurred = str(event["occurred_at"]).replace(" ", "T")[:16]
    if not event:
        occurred = datetime.now().strftime("%Y-%m-%dT%H:%M")
    return [
        {"name": "occurred_at", "label": "Дата/время события", "type": "datetime-local", "value": occurred},
        {
            "name": "description",
            "label": "Описание события",
            "type": "textarea",
            "required": True,
            "value": (event.get("description") if event else "") or "",
        },
        {
            "name": "decision",
            "label": "Принятое решение",
            "type": "textarea",
            "value": (event.get("decision") if event else "") or "",
        },
    ]
