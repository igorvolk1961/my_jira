"""Репозиторий требований (SQL/ORM)."""

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models.projects import Requirement

Row = dict[str, Any]


def list_all(db: Session) -> list[Row]:
    rows = (
        db.execute(
            text(
                "SELECT r.*, p.name AS project_name, s.last_name, s.first_name,"
                " rt.name AS type_name, pr.name AS priority_name"
                " FROM requirement r"
                " JOIN project p ON r.project_id = p.id"
                " LEFT JOIN stakeholder s ON r.stakeholder_id = s.id"
                " JOIN requirement_type rt ON r.requirement_type_id = rt.id"
                " JOIN priority pr ON r.priority_id = pr.id"
                " WHERE r.is_deleted=0"
                " ORDER BY r.id DESC"
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def list_for_project(db: Session, project_id: int) -> list[Row]:
    rows = (
        db.execute(
            text(
                "SELECT r.*, s.last_name, s.first_name, rt.name AS type_name,"
                " pr.name AS priority_name, nrt.name AS nfr_type_name"
                " FROM requirement r"
                " LEFT JOIN stakeholder s ON r.stakeholder_id = s.id"
                " JOIN requirement_type rt ON r.requirement_type_id = rt.id"
                " JOIN priority pr ON r.priority_id = pr.id"
                " LEFT JOIN nonfunctional_requirement_type nrt ON r.nfr_type_id = nrt.id"
                " WHERE r.project_id=:pid AND r.is_deleted=0"
                " ORDER BY r.id DESC"
            ),
            {"pid": project_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get_detail(db: Session, requirement_id: int) -> Row | None:
    row = (
        db.execute(
            text(
                "SELECT r.*, p.name pname, rt.name type_name, pr.name prio, s.last_name, s.first_name,"
                " nrt.name nfr_type_name"
                " FROM requirement r"
                " JOIN project p ON r.project_id=p.id"
                " JOIN requirement_type rt ON r.requirement_type_id=rt.id"
                " JOIN priority pr ON r.priority_id=pr.id"
                " LEFT JOIN stakeholder s ON r.stakeholder_id=s.id"
                " LEFT JOIN nonfunctional_requirement_type nrt ON r.nfr_type_id=nrt.id"
                " WHERE r.id=:rid AND r.is_deleted=0"
            ),
            {"rid": requirement_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_tasks(db: Session, requirement_id: int) -> list[Row]:
    rows = (
        db.execute(
            text(
                "SELECT t.id, t.description, t.deadline, pr.name prio, ts.name st, ts.color color,"
                " pst.name stype"
                " FROM task t"
                " JOIN priority pr ON t.priority_id=pr.id"
                " JOIN task_status ts ON t.status_id=ts.id"
                " LEFT JOIN project_stage ps ON t.stage_id=ps.id"
                " LEFT JOIN project_stage_type pst ON ps.stage_type_id=pst.id"
                " WHERE t.requirement_id=:rid AND t.is_deleted=0"
            ),
            {"rid": requirement_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get(db: Session, requirement_id: int) -> Requirement | None:
    return (
        db.execute(select(Requirement).where(Requirement.id == requirement_id, Requirement.is_deleted == 0))
        .scalars()
        .first()
    )


def create(db: Session, values: dict[str, Any]) -> Requirement:
    item = Requirement(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update(db: Session, item: Requirement, values: dict[str, Any]) -> None:
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()


def soft_delete(db: Session, requirement_id: int) -> None:
    item = get(db, requirement_id)
    if item is not None:
        item.is_deleted = 1
        db.commit()


def link_task(db: Session, task_id: int, requirement_id: int) -> None:
    db.execute(
        text("UPDATE task SET requirement_id=:rid WHERE id=:tid AND is_deleted=0"),
        {"rid": requirement_id, "tid": task_id},
    )
    db.commit()


def form_options(db: Session) -> dict[str, list[Row]]:
    projects = [
        dict(r)
        for r in db.execute(text("SELECT id, name FROM project WHERE is_deleted=0 ORDER BY id")).mappings().all()
    ]
    stakeholders = [
        dict(r)
        for r in db.execute(
            text("SELECT id, last_name, first_name FROM stakeholder WHERE is_deleted=0 ORDER BY last_name")
        )
        .mappings()
        .all()
    ]
    requirement_types = [
        dict(r)
        for r in db.execute(text("SELECT id, name FROM requirement_type WHERE is_deleted=0 ORDER BY id"))
        .mappings()
        .all()
    ]
    nfr_types = [
        dict(r)
        for r in db.execute(text("SELECT id, name FROM nonfunctional_requirement_type WHERE is_deleted=0 ORDER BY id"))
        .mappings()
        .all()
    ]
    priorities = [
        dict(r)
        for r in db.execute(text("SELECT id, name FROM priority WHERE is_deleted=0 ORDER BY id")).mappings().all()
    ]
    return {
        "projects": projects,
        "stakeholders": stakeholders,
        "requirement_types": requirement_types,
        "nfr_types": nfr_types,
        "priorities": priorities,
    }
