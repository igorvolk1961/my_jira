"""Конфигурация приложения: пути, окружение, параметры по умолчанию."""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_DB_NAME = os.environ.get("UPO_DATABASE", "upo_database.db")
AUDIO_DIR = os.environ.get("UPO_AUDIO_DIR", os.path.join(DATABASE_DIR, "audio"))

os.makedirs(DATABASE_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)


def db_path_for(name: str) -> str:
    """Абсолютный путь к файлу БД по имени."""
    return os.path.join(DATABASE_DIR, name)


def secret_key() -> str:
    """Ключ подписи сессии. Без него сессии не сохраняются между перезапусками."""
    value = os.environ.get("UPO_SECRET_KEY")
    if not value:
        import secrets

        value = secrets.token_hex(32)
        print(
            "ВНИМАНИЕ: UPO_SECRET_KEY не задан — используется случайный ключ сессии "
            "(сессии не сохраняются между перезапусками). Для продакшена задайте UPO_SECRET_KEY."
        )
    return value
