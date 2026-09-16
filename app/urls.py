"""Flask-совместимый url_for: относительный путь + лишние параметры как query-string.

Starlette `request.url_for` возвращает абсолютный URL и падает (NoMatchFound) на
параметрах, которых нет в пути. Flask `url_for('endpoint', next='/x')` добавлял их в
query. Здесь восстанавливаем поведение Flask, чтобы ссылки и редиректы совпадали.
"""

from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.routing import APIRoute


def collect_routes(routes):
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from collect_routes(route.original_router.routes)
        elif hasattr(route, "routes"):
            yield from collect_routes(route.routes)


def build_route_param_names(application: FastAPI) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for route in collect_routes(application.routes):
        if route.name:
            mapping[route.name] = set(getattr(route, "param_convertors", {}) or {})
    return mapping


def url_for(request: Request, name: str, /, **params: Any) -> str:
    router = request.scope["router"]
    param_names = getattr(request.app.state, "route_param_names", None) or {}
    path_names = param_names.get(name)
    if path_names is None:
        # Неизвестный маршрут: пусть сработает исключение Starlette (его ловят _url-хелперы).
        return str(router.url_path_for(name, **params))
    path_kwargs = {key: value for key, value in params.items() if key in path_names}
    query_kwargs = {key: value for key, value in params.items() if key not in path_names and value is not None}
    url = str(router.url_path_for(name, **path_kwargs))
    if query_kwargs:
        url += ("&" if "?" in url else "?") + urlencode(query_kwargs)
    return url


def install_relative_url_for() -> None:
    """Monkeypatch: request.url_for снова возвращает относительный путь, как Flask."""
    if getattr(Request.url_for, "_upo_relative", False):
        return

    def _relative_url_for(self: Request, name: str, /, **params: Any) -> str:  # noqa: N807
        return url_for(self, name, **params)

    _relative_url_for._upo_relative = True  # type: ignore[attr-defined]
    Request.url_for = _relative_url_for  # type: ignore[assignment]
