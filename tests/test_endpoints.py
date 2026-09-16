"""Инвариант: набор маршрутов (path, endpoint) не должен меняться при рефакторинге.

Файл tests/endpoints_baseline.txt фиксирует исходный набор. Параметры пути
нормализуются: Flask `<int:id>` == FastAPI `{id}`.
"""

import os
import re
import warnings

from fastapi.routing import APIRoute

from app.main import app

BASELINE = os.path.join(os.path.dirname(__file__), "endpoints_baseline.txt")


def _normalize(path: str) -> str:
    return re.sub(r"<[^>]+>", lambda m: "{" + m.group(0)[1:-1].split(":")[-1] + "}", path)


def _collect(routes):
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from _collect(route.original_router.routes)
        elif hasattr(route, "routes"):
            yield from _collect(route.routes)


def _current() -> list[tuple[str, str]]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sorted((route.path, route.name) for route in _collect(app.routes) if route.name)


def _baseline() -> list[tuple[str, str]]:
    out = []
    with open(BASELINE, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            rule, endpoint = line.split("\t")
            if endpoint == "static":
                continue
            out.append((_normalize(rule), endpoint))
    return sorted(out)


def test_endpoints_match_baseline():
    current = _current()
    base = _baseline()
    missing = sorted(set(base) - set(current))
    added = sorted(set(current) - set(base))
    assert not missing, f"Пропали маршруты: {missing}"
    assert not added, f"Появились новые маршруты: {added}"
    assert len(current) == len(base)


def test_static_is_mounted():
    names = {route.name for route in app.routes if getattr(route, "name", None)}
    assert "static" in names
