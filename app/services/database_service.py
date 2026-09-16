"""Управление базой данных: имена файлов, создание, копирование, переключение, удаление."""

import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from app.config import DEFAULT_DB_NAME, db_path_for
from app.db.backup import backup_database
from app.db.engine import dispose_engine
from app.db.schema import ensure_database
from app.repositories import database_repo

Row = dict[str, Any]
Flash = tuple[str, str]


@dataclass
class DbResult:
    """Результат операции: список flash-сообщений и БД для переключения сессии."""

    flashes: list[Flash] = field(default_factory=list)
    switch_db: str | None = None


def sanitize_db_name(name: str | None) -> str | None:
    value = (name or "").strip()
    if not value or "/" in value or "\\" in value:
        return None
    if not value.endswith(".db"):
        value += ".db"
    if value.startswith(".") or ".." in value:
        return None
    if not all(ch.isalnum() or ch in "_.-" for ch in value):
        return None
    return value


def databases() -> list[Row]:
    return [{"name": name, "size": database_repo.size(db_path_for(name))} for name in database_repo.list_db_files()]


def create(name: str | None) -> DbResult:
    clean = sanitize_db_name(name)
    if not clean:
        return DbResult([("error", "Некорректное имя БД")])
    path = db_path_for(clean)
    if os.path.exists(path):
        ensure_database(path)
        return DbResult([("warning", f"БД «{clean}» уже существует — переключились на неё")], clean)
    ensure_database(path)
    return DbResult([("success", f"Создана БД «{clean}»")], clean)


def copy(source: str | None, name: str | None, switch: bool, current_db: str) -> DbResult:
    source_name = sanitize_db_name(source or current_db)
    clean = sanitize_db_name(name)
    if not source_name or not os.path.exists(db_path_for(source_name)):
        return DbResult([("error", "Исходная БД не найдена")])
    if not clean:
        return DbResult([("error", "Некорректное имя копии")])
    if clean == source_name:
        return DbResult([("error", "Имя копии должно отличаться от исходной БД")])
    dest = db_path_for(clean)
    if os.path.exists(dest):
        return DbResult([("error", f"БД «{clean}» уже существует")])
    source_path = db_path_for(source_name)
    try:
        dispose_engine(source_path)
        database_repo.copy_file(source_path, dest)
        ensure_database(dest)
    except (OSError, sqlite3.Error) as error:
        return DbResult([("error", f"Ошибка копирования: {error}")])
    flashes: list[Flash] = [("success", f"Создана копия «{clean}» из «{source_name}»")]
    switch_db: str | None = None
    if switch:
        switch_db = clean
        flashes.append(("success", f"Активная БД: {clean}"))
    return DbResult(flashes, switch_db)


def use(name: str | None) -> DbResult:
    clean = sanitize_db_name(name)
    if not clean or not os.path.exists(db_path_for(clean)):
        return DbResult([("error", "БД не найдена")])
    ensure_database(db_path_for(clean))
    return DbResult([("success", f"Активная БД: {clean}")], clean)


def delete(name: str | None, current_db: str) -> DbResult:
    clean = sanitize_db_name(name)
    if not clean or not os.path.exists(db_path_for(clean)):
        return DbResult([("error", "БД не найдена")])
    if clean == DEFAULT_DB_NAME:
        return DbResult([("error", "Нельзя удалить основную БД")])
    path = db_path_for(clean)
    try:
        dispose_engine(path)
        database_repo.remove_db_files(path)
    except OSError as error:
        return DbResult([("error", f"Ошибка удаления: {error}")])
    switch_db = DEFAULT_DB_NAME if current_db == clean else None
    return DbResult([("success", f"БД «{clean}» удалена")], switch_db)


def backup(path: str | None = None) -> str | None:
    """Резервная копия БД (делегирует в app.db.backup)."""
    return backup_database(path or db_path_for(DEFAULT_DB_NAME))
