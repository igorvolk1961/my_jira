"""Сервис журнала аудита: разбор фильтров и подготовка данных."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import audit_repo

Row = dict[str, Any]


def _as_int(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def audit_data(db: Session, params: Mapping[str, str]) -> Row:
    project_id = (params.get("project_id") or "").strip()
    position_id = (params.get("position_id") or "").strip()
    user_id = (params.get("user_id") or "").strip()
    sort = params.get("sort") or "created_at"
    direction = params.get("dir") or "desc"
    order_dir = "ASC" if str(direction).lower() == "asc" else "DESC"

    rows = audit_repo.list_logs(
        db,
        project_id=_as_int(project_id),
        position_id=_as_int(position_id),
        user_id=_as_int(user_id),
        sort=sort,
        order_dir=order_dir,
    )
    options = audit_repo.filter_options(db)
    return {
        "rows": rows,
        "projects": options["projects"],
        "positions": options["positions"],
        "users": options["users"],
        "project_id": project_id,
        "position_id": position_id,
        "user_id": user_id,
        "sort": sort,
        "order_dir": order_dir,
    }
