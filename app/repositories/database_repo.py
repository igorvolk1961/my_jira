"""Файловые операции с базами данных SQLite (копирование, удаление, резервные копии)."""

import os
import shutil

from app.config import DATABASE_DIR


def list_db_files() -> list[str]:
    return sorted(f for f in os.listdir(DATABASE_DIR) if f.endswith(".db"))


def size(path: str) -> int:
    return os.path.getsize(path)


def copy_file(source_path: str, dest_path: str) -> None:
    """Снимок файла БД: основной файл и WAL/SHM, если они есть."""
    shutil.copy2(source_path, dest_path)
    for suffix in ("-wal", "-shm"):
        extra = source_path + suffix
        if os.path.exists(extra):
            shutil.copy2(extra, dest_path + suffix)


def remove_db_files(path: str) -> None:
    for suffix in ("", "-wal", "-shm"):
        target = path + suffix
        if os.path.exists(target):
            os.remove(target)
