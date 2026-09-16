"""Репозиторий стейкхолдеров."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_active(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            text(
                """
                SELECT s.*, st.name AS type_name
                FROM stakeholder s
                JOIN stakeholder_type st ON s.type_id = st.id
                WHERE s.is_deleted=0
                ORDER BY s.last_name
                """
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get(db: Session, stakeholder_id: int) -> dict[str, Any] | None:
    row = (
        db.execute(
            text("SELECT * FROM stakeholder WHERE id=:id AND is_deleted=0"),
            {"id": stakeholder_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def get_detail(db: Session, stakeholder_id: int) -> dict[str, Any] | None:
    row = (
        db.execute(
            text(
                """
                SELECT s.*, st.name AS type_name, st.influence_priority AS inf, st.interest_priority AS ints
                FROM stakeholder s
                JOIN stakeholder_type st ON s.type_id = st.id
                WHERE s.id=:id AND s.is_deleted=0
                """
            ),
            {"id": stakeholder_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_types(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(text("SELECT * FROM stakeholder_type WHERE is_deleted=0 ORDER BY id")).mappings().all()
    return [dict(row) for row in rows]


def list_priorities(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(text("SELECT * FROM priority WHERE is_deleted=0 ORDER BY weight")).mappings().all()
    return [dict(row) for row in rows]


def create(db: Session, values: dict[str, Any]) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO stakeholder (last_name, first_name, middle_name, type_id, position, priority, employee_id)
            VALUES (:last_name, :first_name, :middle_name, :type_id, :position, :priority, :employee_id)
            RETURNING id
            """
        ),
        values,
    )
    return int(result.scalar_one())


def update(db: Session, stakeholder_id: int, values: dict[str, Any]) -> None:
    db.execute(
        text(
            """
            UPDATE stakeholder SET last_name=:last_name, first_name=:first_name, middle_name=:middle_name,
                   type_id=:type_id, position=:position, priority=:priority, employee_id=:employee_id,
                   updated_at=CURRENT_TIMESTAMP
            WHERE id=:id
            """
        ),
        {**values, "id": stakeholder_id},
    )


def soft_delete(db: Session, stakeholder_id: int) -> None:
    db.execute(
        text("UPDATE stakeholder SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
        {"id": stakeholder_id},
    )


def linked_employee_ids(db: Session) -> set[int]:
    rows = (
        db.execute(text("SELECT DISTINCT employee_id FROM stakeholder WHERE employee_id IS NOT NULL AND is_deleted=0"))
        .scalars()
        .all()
    )
    return {int(value) for value in rows}


def available_employees(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(text("SELECT * FROM employee WHERE is_deleted=0 ORDER BY last_name")).mappings().all()
    return [dict(row) for row in rows]


def employee_by_id(db: Session, employee_id: int) -> dict[str, Any] | None:
    row = (
        db.execute(
            text("SELECT * FROM employee WHERE id=:id AND is_deleted=0"),
            {"id": employee_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def add_project_stakeholder(db: Session, project_id: int, stakeholder_id: int) -> None:
    db.execute(
        text("INSERT INTO project_stakeholder (project_id, stakeholder_id) VALUES (:pid, :sid)"),
        {"pid": project_id, "sid": stakeholder_id},
    )


def detail_projects(db: Session, stakeholder_id: int) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            text(
                """
                SELECT p.id, p.name, pr.name AS prio, p.deadline
                FROM project p
                JOIN priority pr ON p.priority_id = pr.id
                WHERE p.main_stakeholder_id=:id AND p.is_deleted=0
                ORDER BY p.id
                """
            ),
            {"id": stakeholder_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def detail_requirements(db: Session, stakeholder_id: int) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            text(
                """
                SELECT r.id, r.description, p.name AS pname, rt.name AS type_name, pr.name AS prio
                FROM requirement r
                JOIN project p ON r.project_id = p.id
                JOIN requirement_type rt ON r.requirement_type_id = rt.id
                JOIN priority pr ON r.priority_id = pr.id
                WHERE r.stakeholder_id=:id AND r.is_deleted=0
                ORDER BY r.id DESC
                """
            ),
            {"id": stakeholder_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def detail_interviews(db: Session, stakeholder_id: int) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            text(
                """
                SELECT i.* FROM interview i
                WHERE i.stakeholder_id=:id AND i.is_deleted=0
                ORDER BY i.scheduled_at DESC
                """
            ),
            {"id": stakeholder_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
