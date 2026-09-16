"""Репозиторий проектов (SQL/ORM)."""

from typing import Any

from sqlalchemy import bindparam, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.projects import Project, ProjectEmployee, ProjectStakeholder

Row = dict[str, Any]


def list_active(db: Session) -> list[dict[str, object]]:
    rows = db.execute(text("SELECT id, name FROM project WHERE is_deleted=0 ORDER BY id")).mappings().all()
    return [dict(row) for row in rows]


def list_with_refs(db: Session) -> list[Row]:
    rows = (
        db.execute(
            text(
                "SELECT p.*, s.last_name, s.first_name, pr.name as priority_name, pr.weight"
                " FROM project p"
                " LEFT JOIN stakeholder s ON p.main_stakeholder_id = s.id"
                " JOIN priority pr ON p.priority_id = pr.id"
                " WHERE p.is_deleted=0"
                " ORDER BY p.id DESC"
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get(db: Session, project_id: int) -> Project | None:
    return db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == 0)).scalars().first()


def get_detail(db: Session, project_id: int) -> Row | None:
    row = (
        db.execute(
            text(
                "SELECT p.*, s.last_name, s.first_name, pr.name as priority_name, pr.weight"
                " FROM project p"
                " LEFT JOIN stakeholder s ON p.main_stakeholder_id = s.id"
                " JOIN priority pr ON p.priority_id = pr.id"
                " WHERE p.id=:pid AND p.is_deleted=0"
            ),
            {"pid": project_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def create(db: Session, values: dict[str, Any]) -> Project:
    item = Project(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update(db: Session, item: Project, values: dict[str, Any]) -> None:
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()


def soft_delete(db: Session, project_id: int) -> None:
    item = get(db, project_id)
    if item is not None:
        item.is_deleted = 1
        db.commit()


def form_options(db: Session) -> dict[str, list[Row]]:
    stakeholders = [
        dict(r)
        for r in db.execute(
            text("SELECT id, last_name, first_name FROM stakeholder WHERE is_deleted=0 ORDER BY last_name")
        )
        .mappings()
        .all()
    ]
    priorities = [
        dict(r)
        for r in db.execute(text("SELECT id, name, weight FROM priority WHERE is_deleted=0 ORDER BY id"))
        .mappings()
        .all()
    ]
    return {"stakeholders": stakeholders, "priorities": priorities}


def stakeholder_data(db: Session, project_id: int) -> dict[str, Any]:
    project = (
        db.execute(text("SELECT id, main_stakeholder_id FROM project WHERE id=:pid"), {"pid": project_id})
        .mappings()
        .first()
    )
    main_id = int(project["main_stakeholder_id"]) if project and project["main_stakeholder_id"] else None
    assoc_rows = (
        db.execute(
            text("SELECT stakeholder_id FROM project_stakeholder WHERE project_id=:pid AND is_deleted=0"),
            {"pid": project_id},
        )
        .mappings()
        .all()
    )
    assoc_ids = {int(a["stakeholder_id"]) for a in assoc_rows}
    req_st_ids = {
        int(row[0])
        for row in db.execute(
            text(
                "SELECT DISTINCT stakeholder_id FROM requirement"
                " WHERE project_id=:pid AND stakeholder_id IS NOT NULL AND is_deleted=0"
            ),
            {"pid": project_id},
        ).fetchall()
        if row[0] is not None
    }
    stk_ids = set(assoc_ids)
    if main_id:
        stk_ids.add(main_id)
    stk_ids |= req_st_ids

    rows: list[Row] = []
    if stk_ids:
        rows = [
            dict(r)
            for r in db.execute(
                text(
                    "SELECT s.*, st.name type_name, st.influence_priority inf, st.interest_priority ints,"
                    " (SELECT COUNT(*) FROM requirement r"
                    "  WHERE r.stakeholder_id=s.id AND r.project_id=:pid AND r.is_deleted=0) req_count"
                    " FROM stakeholder s JOIN stakeholder_type st ON s.type_id=st.id"
                    " WHERE s.is_deleted=0 AND s.id IN :ids"
                    " ORDER BY s.last_name"
                ).bindparams(bindparam("ids", expanding=True)),
                {"pid": project_id, "ids": sorted(stk_ids)},
            )
            .mappings()
            .all()
        ]

    if stk_ids:
        candidates = [
            dict(r)
            for r in db.execute(
                text(
                    "SELECT s.*, st.name type_name FROM stakeholder s JOIN stakeholder_type st ON s.type_id=st.id"
                    " WHERE s.is_deleted=0 AND s.id NOT IN :ids ORDER BY s.last_name"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": sorted(stk_ids)},
            )
            .mappings()
            .all()
        ]
    else:
        candidates = [
            dict(r)
            for r in db.execute(
                text(
                    "SELECT s.*, st.name type_name FROM stakeholder s JOIN stakeholder_type st ON s.type_id=st.id"
                    " WHERE s.is_deleted=0 ORDER BY s.last_name"
                )
            )
            .mappings()
            .all()
        ]
    return {"rows": rows, "candidates": candidates, "assoc_ids": assoc_ids, "main_id": main_id}


def add_stakeholder(db: Session, project_id: int, stakeholder_id: int) -> bool:
    db.add(ProjectStakeholder(project_id=project_id, stakeholder_id=stakeholder_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def remove_stakeholder(db: Session, project_id: int, stakeholder_id: int) -> None:
    db.execute(
        text(
            "UPDATE project_stakeholder SET is_deleted=1, updated_at=CURRENT_TIMESTAMP"
            " WHERE project_id=:pid AND stakeholder_id=:sid"
        ),
        {"pid": project_id, "sid": stakeholder_id},
    )
    db.commit()


def list_employees(db: Session, project_id: int) -> list[Row]:
    rows = (
        db.execute(
            text(
                "SELECT e.*, pe.project_id, pt.name position_name, es.name status_name, es.is_available"
                " FROM project_employee pe"
                " JOIN employee e ON pe.employee_id=e.id"
                " JOIN position_type pt ON e.position_type_id=pt.id"
                " JOIN employee_status es ON e.status_id=es.id"
                " WHERE pe.project_id=:pid AND pe.is_deleted=0 AND e.is_deleted=0"
                " ORDER BY e.last_name"
            ),
            {"pid": project_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def list_employee_candidates(db: Session, project_id: int) -> list[Row]:
    emp_ids = [int(e["id"]) for e in list_employees(db, project_id)]
    if emp_ids:
        return [
            dict(r)
            for r in db.execute(
                text(
                    "SELECT e.*, pt.name position_name FROM employee e"
                    " JOIN position_type pt ON e.position_type_id=pt.id"
                    " WHERE e.is_deleted=0 AND e.id NOT IN :ids ORDER BY e.last_name"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": emp_ids},
            )
            .mappings()
            .all()
        ]
    return [
        dict(r)
        for r in db.execute(
            text(
                "SELECT e.*, pt.name position_name FROM employee e"
                " JOIN position_type pt ON e.position_type_id=pt.id"
                " WHERE e.is_deleted=0 ORDER BY e.last_name"
            )
        )
        .mappings()
        .all()
    ]


def add_employee(db: Session, project_id: int, employee_id: int) -> bool:
    db.add(ProjectEmployee(project_id=project_id, employee_id=employee_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def remove_employee(db: Session, project_id: int, employee_id: int) -> None:
    db.execute(
        text(
            "UPDATE project_employee SET is_deleted=1, updated_at=CURRENT_TIMESTAMP"
            " WHERE project_id=:pid AND employee_id=:eid"
        ),
        {"pid": project_id, "eid": employee_id},
    )
    db.commit()
