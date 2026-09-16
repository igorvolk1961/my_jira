"""Репозиторий журнала аудита: выборки с фильтрами и сортировкой."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

Row = dict[str, Any]

_SORTS = {
    "created_at": "a.created_at",
    "user": "user_name",
    "action": "a.action",
    "project": "project_name",
}


def _assigner_sql(emp_alias: str, user_alias: str, extra_fallback: str) -> str:
    parts = [f"TRIM({emp_alias}.last_name || ' ' || {emp_alias}.first_name)"]
    parts.append(extra_fallback)
    parts.append(f"{user_alias}.login")
    parts.append("'—'")
    return "COALESCE(" + ", ".join(parts) + ")"


def list_logs(
    db: Session,
    *,
    project_id: int | None,
    position_id: int | None,
    user_id: int | None,
    sort: str,
    order_dir: str,
) -> list[Row]:
    order_col = _SORTS.get(sort, "a.created_at")
    direction = "ASC" if order_dir == "ASC" else "DESC"

    where: list[str] = []
    params: dict[str, int] = {}
    if project_id is not None:
        where.append("a.project_id=:project_id")
        params["project_id"] = project_id
    if position_id is not None:
        where.append("a.position_id=:position_id")
        params["position_id"] = position_id
    if user_id is not None:
        where.append("a.user_id=:user_id")
        params["user_id"] = user_id
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = (
        db.execute(
            text(
                f"""
                SELECT a.*, u.login,
                       {_assigner_sql("ae", "u", "a.user_login")} AS user_name,
                       p.name AS project_name,
                       pt.name AS position_name
                FROM audit_log a
                LEFT JOIN app_user u ON a.user_id = u.id
                LEFT JOIN employee ae ON u.employee_id = ae.id
                LEFT JOIN project p ON a.project_id = p.id
                LEFT JOIN position_type pt ON a.position_id = pt.id
                {where_sql}
                ORDER BY {order_col} {direction}, a.id {direction}
                LIMIT 1000
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def filter_options(db: Session) -> dict[str, list[Row]]:
    projects = [
        dict(row)
        for row in db.execute(text("SELECT id, name FROM project WHERE is_deleted=0 ORDER BY name")).mappings().all()
    ]
    positions = [
        dict(row)
        for row in db.execute(text("SELECT id, name FROM position_type WHERE is_deleted=0 ORDER BY name"))
        .mappings()
        .all()
    ]
    users = [
        dict(row)
        for row in db.execute(
            text(
                """
                SELECT u.id, u.login,
                       COALESCE(TRIM(e.last_name || ' ' || e.first_name), u.login) AS name
                FROM app_user u LEFT JOIN employee e ON u.employee_id=e.id
                WHERE u.is_deleted=0 ORDER BY name
                """
            )
        )
        .mappings()
        .all()
    ]
    return {"projects": projects, "positions": positions, "users": users}
