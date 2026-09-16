"""FastAPI-зависимости: сессия БД, текущий пользователь, проверки прав, текущий проект."""

import os
from collections.abc import Iterator
from typing import Any

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import DEFAULT_DB_NAME, db_path_for
from app.db.engine import get_session_factory
from app.db.schema import ensure_database
from app.errors import AuthRedirect, ForbiddenRedirect

User = dict[str, Any]


def current_db_name(request: Request) -> str:
    return str(request.session.get("db_name", DEFAULT_DB_NAME))


def get_db(request: Request) -> Iterator[Session]:
    """Сессия SQLAlchemy для активной БД текущей сессии."""
    path = db_path_for(current_db_name(request))
    if not os.path.exists(path):
        ensure_database(path)
    session = get_session_factory(path)()
    try:
        yield session
    finally:
        session.close()


def _next_url(request: Request) -> str:
    url = str(request.url.path)
    if request.url.query:
        url += "?" + request.url.query
    return url


def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Текущий пользователь (dict) или None. Кэшируется на время запроса."""
    if getattr(request.state, "current_user_loaded", False):
        return request.state.current_user
    request.state.current_user_loaded = True
    request.state.current_user = None

    uid = request.session.get("user_id")
    if not uid:
        return None
    row = (
        db.execute(
            text(
                "SELECT u.*, e.last_name, e.first_name, e.middle_name, e.position_type_id,"
                " pt.name AS position_name"
                " FROM app_user u"
                " LEFT JOIN employee e ON u.employee_id=e.id"
                " LEFT JOIN position_type pt ON e.position_type_id=pt.id"
                " WHERE u.id=:uid AND u.is_deleted=0"
            ),
            {"uid": uid},
        )
        .mappings()
        .first()
    )
    if row:
        full_name = " ".join(x for x in (row["last_name"], row["first_name"], row["middle_name"]) if x) or row["login"]
        request.state.current_user = {
            "id": row["id"],
            "login": row["login"],
            "role": row["role"],
            "is_analyst": row["is_analyst"],
            "employee_id": row["employee_id"],
            "position_id": row["position_type_id"],
            "position_name": row["position_name"],
            "full_name": full_name,
        }
    return request.state.current_user


def require_user(request: Request, user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise AuthRedirect(_next_url(request))
    return user


def require_admin(request: Request, user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise AuthRedirect(_next_url(request))
    if user.get("role") != "admin":
        raise ForbiddenRedirect("Недостаточно прав: требуется роль администратора")
    return user


def require_analyst_or_admin(request: Request, user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise AuthRedirect(_next_url(request))
    if not (user.get("role") == "admin" or user.get("is_analyst")):
        raise ForbiddenRedirect("Недостаточно прав: требуется роль системного аналитика")
    return user


def current_project(request: Request, db: Session = Depends(get_db)) -> dict[str, Any] | None:
    """Текущий проект из сессии; при отсутствии/невалидности — первый активный."""
    if getattr(request.state, "current_project_loaded", False):
        return request.state.current_project
    request.state.current_project_loaded = True
    request.state.current_project = None

    pid = request.session.get("project_id")
    row = None
    if pid:
        row = db.execute(text("SELECT * FROM project WHERE id=:pid AND is_deleted=0"), {"pid": pid}).mappings().first()
    if not row:
        row = db.execute(text("SELECT * FROM project WHERE is_deleted=0 ORDER BY id LIMIT 1")).mappings().first()
        request.session["project_id"] = row["id"] if row else None
    request.state.current_project = dict(row) if row else None
    return request.state.current_project
