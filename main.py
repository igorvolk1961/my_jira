"""Точка входа приложения (FastAPI) и совместимые хелперы для тестов/скриптов."""

from app.config import (  # noqa: F401
    AUDIO_DIR,
    BASE_DIR,
    DATABASE_DIR,
    DEFAULT_DB_NAME,
    db_path_for,
)
from app.db.schema import ensure_database as init_db  # noqa: F401
from app.main import app  # noqa: F401


def test_client():
    """Клиент для тестов/скриптов (аналог Flask test_client)."""
    from fastapi.testclient import TestClient

    return TestClient(app, follow_redirects=False)


if __name__ == "__main__":
    import os

    import uvicorn

    print("=" * 60)
    print(f"Учебный проектный офис (УПО) запущен! Активная БД: {DEFAULT_DB_NAME}")
    print("=" * 60)
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        reload=os.environ.get("UPO_DEBUG", "") == "1",
    )
