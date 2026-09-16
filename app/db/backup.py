"""Резервное копирование SQLite-БД (поведение legacy backup_db)."""

import os
import shutil
from datetime import datetime

from sqlalchemy import text

from app.config import DATABASE_DIR
from app.db.engine import get_engine


def backup_database(path: str) -> str | None:
    """Копирует существующую инициализированную БД в data/backups/. Возвращает путь копии."""
    if not path or not os.path.exists(path):
        return None
    try:
        engine = get_engine(path)
        with engine.connect() as conn:
            has_tables = conn.execute(
                text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='priority'")
            ).scalar_one()
        if not has_tables:
            return None
        backup_dir = os.path.join(DATABASE_DIR, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = os.path.join(backup_dir, f"{os.path.basename(path)}_{timestamp}.db")
        shutil.copy2(path, destination)
        return destination
    except Exception:  # noqa: BLE001 - резервное копирование не должно мешать запуску
        return None
