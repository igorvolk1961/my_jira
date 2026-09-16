"""Проверка направления зависимостей между слоями (без импорта приложения)."""

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[2] / "app"


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _files(subdir: str) -> list[pathlib.Path]:
    return sorted((APP / subdir).glob("*.py"))


def test_controllers_do_not_import_repositories():
    offenders = {}
    for path in _files("api"):
        bad = {m for m in _imports(path) if m == "app.repositories" or m.startswith("app.repositories.")}
        if bad:
            offenders[path.name] = sorted(bad)
    assert not offenders, f"api не должен зависеть от repositories: {offenders}"


def test_services_do_not_import_web_framework():
    offenders = {}
    for path in _files("services"):
        bad = {m for m in _imports(path) if m.split(".")[0] in {"fastapi", "starlette", "jinja2"}}
        if bad:
            offenders[path.name] = sorted(bad)
    assert not offenders, f"services не должны зависеть от FastAPI/Jinja: {offenders}"


def test_repositories_do_not_import_web_framework():
    offenders = {}
    for path in _files("repositories"):
        bad = {m for m in _imports(path) if m.split(".")[0] in {"fastapi", "starlette", "jinja2"}}
        if bad:
            offenders[path.name] = sorted(bad)
    assert not offenders, f"repositories не должны зависеть от FastAPI/Jinja: {offenders}"
