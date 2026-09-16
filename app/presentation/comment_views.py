"""Построение HTML для комментариев (без SQL и бизнес-логики)."""

import html
from typing import Any

from fastapi import Request

TYPE_TITLES = {"task": "Задача", "subtask": "Подзадача"}


def _url(request: Request, name: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return "#"


def entity_title(entity_type: str, entity_id: int | None) -> str:
    prefix = TYPE_TITLES.get(entity_type, "Сущность")
    return f"{prefix} #{entity_id}"


def form_context(
    entity_type: str,
    entity_id: int | None,
    label: str | None,
    author: str,
) -> dict[str, Any]:
    fixed = bool(entity_type and entity_id)
    return {
        "entity_type": entity_type or "task",
        "entity_id": entity_id,
        "entity_label": html.escape(label) if label else "—",
        "entity_title": entity_title(entity_type, entity_id) if fixed else "—",
        "fixed": fixed,
        "author": author,
    }
