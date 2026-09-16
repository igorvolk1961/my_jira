"""Создание и миграция схемы БД через Alembic + начальное заполнение."""

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.schema import CreateColumn

import app.db.models  # noqa: F401  (регистрирует все таблицы в metadata)
from app.config import BASE_DIR, DEFAULT_DB_NAME, db_path_for
from app.db.backup import backup_database
from app.db.base import Base
from app.db.engine import get_engine
from app.db.seed import seed_database

MIGRATIONS_DIR = os.path.join(BASE_DIR, "app", "db", "migrations")


def _alembic_config(path: str) -> Config:
    cfg = Config(os.path.join(BASE_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", MIGRATIONS_DIR)
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
    return cfg


def _table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def _reconcile_schema(engine: Engine) -> None:
    """Аддитивно дополняет существующую БД до текущих моделей: таблицы и колонки."""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {ddl}"))


def ensure_database(path: str | None = None) -> str:
    """Приводит БД к актуальной схеме и заполняет справочники. Возвращает путь."""
    path = path or db_path_for(DEFAULT_DB_NAME)
    engine = get_engine(path)
    tables = _table_names(engine)
    cfg = _alembic_config(path)

    if tables:
        backup_database(path)

    if "alembic_version" not in tables and tables:
        # Легаси-БД: сначала аддитивно доводим схему, заполняем справочники и только
        # затем помечаем baseline (чтобы неудачная миграция не оставила ложный head).
        _reconcile_schema(engine)
        seed_database(engine)
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")
        seed_database(engine)
    return path
