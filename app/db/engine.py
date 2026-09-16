"""Реестр SQLAlchemy engine/session по файлам БД.

Приложение работает с несколькими SQLite-файлами одновременно (переключение «активной»
БД в сессии), поэтому engine кэшируется по абсолютному пути к файлу.
"""

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

_engines: dict[str, Engine] = {}
_factories: dict[str, sessionmaker[Session]] = {}


def _normalize(path: str) -> str:
    return str(Path(path).resolve())


def get_engine(path: str) -> Engine:
    key = _normalize(path)
    engine = _engines.get(key)
    if engine is None:
        engine = create_engine(
            f"sqlite+pysqlite:///{key}",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )

        @event.listens_for(engine, "connect")
        def _set_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()

        _engines[key] = engine
        _factories[key] = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    return engine


def get_session_factory(path: str) -> sessionmaker[Session]:
    get_engine(path)
    return _factories[_normalize(path)]


def dispose_engine(path: str) -> None:
    key = _normalize(path)
    engine = _engines.pop(key, None)
    _factories.pop(key, None)
    if engine is not None:
        engine.dispose()


def dispose_all() -> None:
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()
    _factories.clear()
