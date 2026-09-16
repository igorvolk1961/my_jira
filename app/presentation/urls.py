"""Безопасное построение URL в presentation-слое (устойчиво к частичной миграции)."""

from typing import Any

from fastapi import Request


def safe_url(request: Request, name: str, **params: Any) -> str | None:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return None


def url_or(request: Request, name: str, fallback: str = "#", **params: Any) -> str:
    return safe_url(request, name, **params) or fallback
