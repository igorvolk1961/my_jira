"""Пароли, безопасные редиректы, метки ролей.

Пароли хранятся как PBKDF2-HMAC-SHA256: ``pbkdf2_sha256$<iterations>$<salt>$<hash>``.
Старые plaintext-значения поддерживаются на чтение и заменяются хешем при успешном входе.
"""

import hashlib
import hmac
import secrets
from urllib.parse import urlsplit

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 260_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_hex(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt}${digest.hex()}"


def is_password_hash(stored: str | None) -> bool:
    if not stored:
        return False
    return stored.startswith(f"{_ALGO}$") and stored.count("$") == 3


def verify_password(stored: str | None, password: str) -> bool:
    """Проверяет пароль. Для plaintext-значения — прямое сравнение (миграция на хеш в сервисе)."""
    if stored is None:
        return False
    if is_password_hash(stored):
        _, iterations, salt, digest = stored.split("$", 3)
        try:
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        except ValueError:
            return False
        return hmac.compare_digest(candidate.hex(), digest)
    return hmac.compare_digest(stored, password)


def safe_next(value: str | None, fallback: str) -> str:
    """Возвращает value, только если это локальный путь (защита от open redirect)."""
    if value and isinstance(value, str) and "\\" not in value:
        parts = urlsplit(value)
        if not parts.scheme and not parts.netloc and value.startswith("/") and not value.startswith("//"):
            return value
    return fallback


def role_label(role: str | None, is_analyst_flag: bool = False) -> str:
    labels = {"admin": "администратор", "user": "пользователь"}
    parts = [labels.get(role or "", role or "—")]
    if is_analyst_flag:
        parts.append("системный аналитик")
    return ", ".join(parts)
