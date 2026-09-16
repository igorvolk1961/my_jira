"""Артефакты СА и пользовательские истории: доступ к данным (SQL/ORM)."""

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models.artifacts import UserStory, UserStorySection

Row = dict[str, Any]


def get_artifact(db: Session, project_id: int, key: str) -> Row | None:
    row = (
        db.execute(
            text("SELECT * FROM project_artifact WHERE project_id=:pid AND artifact_key=:key AND is_deleted=0"),
            {"pid": project_id, "key": key},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def upsert_artifact(db: Session, project_id: int, key: str, content: str, user_id: int | None) -> None:
    db.execute(
        text(
            "INSERT INTO project_artifact (project_id, artifact_key, content, updated_by_user_id)"
            " VALUES (:pid, :key, :content, :uid)"
            " ON CONFLICT(project_id, artifact_key) DO UPDATE SET"
            " content=excluded.content,"
            " updated_by_user_id=excluded.updated_by_user_id,"
            " is_deleted=0,"
            " updated_at=CURRENT_TIMESTAMP"
        ),
        {"pid": project_id, "key": key, "content": content, "uid": user_id},
    )
    db.commit()


def clear_artifact(db: Session, project_id: int, key: str) -> None:
    db.execute(
        text(
            "UPDATE project_artifact SET content=NULL, updated_at=CURRENT_TIMESTAMP"
            " WHERE project_id=:pid AND artifact_key=:key"
        ),
        {"pid": project_id, "key": key},
    )
    db.commit()


def list_user_stories(db: Session, project_id: int) -> list[Row]:
    rows = (
        db.execute(
            text(
                "SELECT us.*, st.name AS stakeholder_type_name"
                " FROM user_story us"
                " LEFT JOIN stakeholder_type st ON us.stakeholder_type_id = st.id"
                " WHERE us.project_id=:pid AND us.is_deleted=0"
                " ORDER BY us.position, us.id"
            ),
            {"pid": project_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def list_sections(db: Session, project_id: int) -> list[Row]:
    rows = (
        db.execute(
            text("SELECT * FROM user_story_section WHERE project_id=:pid AND is_deleted=0 ORDER BY position, id"),
            {"pid": project_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def list_stakeholder_types(db: Session) -> list[Row]:
    rows = db.execute(text("SELECT * FROM stakeholder_type WHERE is_deleted=0 ORDER BY id")).mappings().all()
    return [dict(row) for row in rows]


def next_story_identifier(db: Session, project_id: int) -> str:
    value = db.execute(
        text(
            "SELECT COALESCE(MAX(CAST(SUBSTR(identifier, 4) AS INTEGER)), 0) + 1"
            " FROM user_story WHERE project_id=:pid AND identifier LIKE 'US-%'"
        ),
        {"pid": project_id},
    ).scalar()
    return f"US-{int(value or 1)}"


def next_story_position(db: Session, project_id: int) -> int:
    value = db.execute(
        text("SELECT COALESCE(MAX(position), -1) + 1 FROM user_story WHERE project_id=:pid"),
        {"pid": project_id},
    ).scalar()
    return int(value or 0)


def create_story(db: Session, values: dict[str, Any]) -> None:
    db.add(UserStory(**values))
    db.commit()


def get_story(db: Session, story_id: int) -> Row | None:
    row = (
        db.execute(
            text("SELECT * FROM user_story WHERE id=:i AND is_deleted=0"),
            {"i": story_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def update_story(db: Session, story_id: int, values: dict[str, Any]) -> None:
    item = db.execute(select(UserStory).where(UserStory.id == story_id)).scalars().first()
    if item is None:
        return
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()


def soft_delete_story(db: Session, story_id: int) -> None:
    db.execute(
        text("UPDATE user_story SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:i"),
        {"i": story_id},
    )
    db.commit()


def valid_section_id(db: Session, project_id: int, value: object) -> int | None:
    try:
        section_id = int(str(value))
    except (TypeError, ValueError):
        return None
    found = db.execute(
        text("SELECT 1 FROM user_story_section WHERE id=:i AND project_id=:pid AND is_deleted=0"),
        {"i": section_id, "pid": project_id},
    ).first()
    return section_id if found else None


def next_section_position(db: Session, project_id: int) -> int:
    value = db.execute(
        text("SELECT COALESCE(MAX(position), -1) + 1 FROM user_story_section WHERE project_id=:pid"),
        {"pid": project_id},
    ).scalar()
    return int(value or 0)


def create_section(db: Session, project_id: int, name: str, position: int) -> None:
    db.add(UserStorySection(project_id=project_id, name=name, position=position))
    db.commit()


def get_section(db: Session, section_id: int) -> Row | None:
    row = (
        db.execute(
            text("SELECT * FROM user_story_section WHERE id=:i AND is_deleted=0"),
            {"i": section_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def rename_section(db: Session, section_id: int, name: str) -> None:
    db.execute(
        text("UPDATE user_story_section SET name=:n, updated_at=CURRENT_TIMESTAMP WHERE id=:i"),
        {"n": name, "i": section_id},
    )
    db.commit()


def section_has_children(db: Session, section_id: int) -> bool:
    found = db.execute(
        text("SELECT 1 FROM user_story_section WHERE parent_id=:i AND is_deleted=0 LIMIT 1"),
        {"i": section_id},
    ).first()
    return found is not None


def section_has_stories(db: Session, section_id: int) -> bool:
    found = db.execute(
        text("SELECT 1 FROM user_story WHERE section_id=:i AND is_deleted=0 LIMIT 1"),
        {"i": section_id},
    ).first()
    return found is not None


def soft_delete_section(db: Session, section_id: int) -> None:
    db.execute(
        text("UPDATE user_story_section SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:i"),
        {"i": section_id},
    )
    db.commit()


def set_section_position(db: Session, section_id: int, project_id: int, position: int) -> None:
    db.execute(
        text("UPDATE user_story_section SET position=:p WHERE id=:i AND project_id=:pid"),
        {"p": position, "i": section_id, "pid": project_id},
    )


def set_story_order(db: Session, story_id: int, project_id: int, position: int, section_id: int | None) -> None:
    db.execute(
        text("UPDATE user_story SET position=:p, section_id=:sid WHERE id=:i AND project_id=:pid"),
        {"p": position, "sid": section_id, "i": story_id, "pid": project_id},
    )


def commit(db: Session) -> None:
    db.commit()


def find_requirement_type_id(db: Session, name: str) -> int | None:
    value = db.execute(
        text("SELECT id FROM requirement_type WHERE lower(name)=lower(:n) AND is_deleted=0"),
        {"n": name},
    ).scalar()
    return int(value) if value is not None else None


def list_requirements(db: Session, project_id: int, type_id: int | None = None) -> list[Row]:
    params: dict[str, Any] = {"pid": project_id}
    type_filter = ""
    if type_id:
        type_filter = " AND rt.id=:tid"
        params["tid"] = type_id
    rows = (
        db.execute(
            text(
                "SELECT r.*, s.last_name, s.first_name, rt.name as type_name,"
                " pr.name as priority_name, nrt.name as nfr_type_name"
                " FROM requirement r"
                " LEFT JOIN stakeholder s ON r.stakeholder_id = s.id"
                " JOIN requirement_type rt ON r.requirement_type_id = rt.id"
                " JOIN priority pr ON r.priority_id = pr.id"
                " LEFT JOIN nonfunctional_requirement_type nrt ON r.nfr_type_id = nrt.id"
                " WHERE r.project_id=:pid AND r.is_deleted=0" + type_filter + " ORDER BY r.id DESC"
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
