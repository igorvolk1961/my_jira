"""Аутентификация и регистрация."""

from sqlalchemy.orm import Session

from app.db.models.system import AppUser
from app.repositories import user_repo
from app.security import hash_password, is_password_hash, verify_password


def authenticate(db: Session, login: str, password: str) -> AppUser | None:
    """Проверяет логин/пароль. Прозрачно мигрирует plaintext-пароль в хеш."""
    user = user_repo.find_by_login(db, login)
    if user is None or not verify_password(user.password, password):
        return None
    if not is_password_hash(user.password):
        user.password = hash_password(password)
        db.commit()
    return user


def register(
    db: Session, login: str, password: str, last_name: str, first_name: str, middle_name: str
) -> tuple[AppUser | None, str]:
    """Регистрирует пользователя. Возвращает (user, error_message)."""
    if not (login and password and last_name and first_name and middle_name):
        return None, "Все поля обязательны, пароль не может быть пустым"
    if user_repo.find_by_login(db, login, include_deleted=True) is not None:
        return None, "Пользователь с таким логином уже существует"
    employee = user_repo.create_employee(db, last_name, first_name, middle_name)
    user = user_repo.create_user(db, login, hash_password(password), "user", employee.id)
    db.commit()
    return user, ""
