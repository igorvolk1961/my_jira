"""Артефакты СА и пользовательские истории: бизнес-логика."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import artifact_repo
from app.services import project_service, stage_service

Row = dict[str, Any]

ARTIFACTS: list[Row] = [
    {"key": "vision", "title": "Видение (Vision)", "kind": "document"},
    {"key": "glossary", "title": "Глоссарий", "kind": "document"},
    {"key": "stakeholders", "title": "Заинтересованные лица", "kind": "stakeholders"},
    {"key": "personas", "title": "Персоны", "kind": "document"},
    {"key": "user_stories", "title": "Пользовательские истории", "kind": "user_stories"},
    {"key": "use_cases", "title": "Варианты использования", "kind": "document"},
    {
        "key": "functional_requirements",
        "title": "Функциональные требования",
        "kind": "requirements",
        "req_type": "Функциональное требование",
    },
    {
        "key": "nonfunctional_requirements",
        "title": "Нефункциональные требования",
        "kind": "requirements",
        "req_type": "Нефункциональное требование",
    },
    {"key": "bpmn", "title": "Модель бизнес-процессов (BPMN)", "kind": "bpmn"},
    {"key": "state_machines", "title": "Диаграммы состояний", "kind": "document"},
    {"key": "data_model", "title": "Модель данных (ER)", "kind": "document"},
    {"key": "prototype", "title": "Прототип и навигация", "kind": "document"},
    {"key": "backlog", "title": "Бэклог и критерии приёмки", "kind": "backlog"},
    {"key": "risks", "title": "Риски и допущения", "kind": "document"},
]

ARTIFACTS_BY_KEY: dict[str, Row] = {artifact["key"]: artifact for artifact in ARTIFACTS}

EDITABLE_KINDS = ("document", "bpmn")


def content(db: Session, project_id: int, key: str) -> str:
    row = artifact_repo.get_artifact(db, project_id, key)
    if row and row.get("content"):
        return str(row["content"])
    return ""


def save_document(db: Session, project_id: int, key: str, text: str, user_id: int | None) -> None:
    artifact_repo.upsert_artifact(db, project_id, key, text, user_id)


def clear_artifact(db: Session, project_id: int, key: str) -> None:
    artifact_repo.clear_artifact(db, project_id, key)


def body_data(db: Session, artifact: Mapping[str, Any], project_id: int) -> Row:
    """Данные для тела страницы артефакта (в зависимости от его вида)."""
    kind = artifact["kind"]
    if kind == "user_stories":
        return {
            "kind": kind,
            "stories": artifact_repo.list_user_stories(db, project_id),
            "sections": artifact_repo.list_sections(db, project_id),
            "types": artifact_repo.list_stakeholder_types(db),
        }
    if kind == "stakeholders":
        return {"kind": kind, "stakeholders": project_service.stakeholder_data(db, project_id)}
    if kind == "backlog":
        return {"kind": kind, "tree": stage_service.project_tree(db, project_id)}
    if kind == "requirements":
        type_id = artifact_repo.find_requirement_type_id(db, str(artifact.get("req_type") or ""))
        return {
            "kind": kind,
            "type_id": type_id,
            "requirements": artifact_repo.list_requirements(db, project_id, type_id),
            "show_nfr_type": artifact["key"] == "nonfunctional_requirements",
        }
    return {"kind": kind, "row": artifact_repo.get_artifact(db, project_id, artifact["key"])}


def _to_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _stakeholder_type_id(value: Any) -> int | None:
    return _to_int(value)


def create_story(db: Session, project_id: int, form: Mapping[str, Any]) -> None:
    identifier = str(form.get("identifier") or "").strip() or artifact_repo.next_story_identifier(db, project_id)
    values: Row = {
        "project_id": project_id,
        "section_id": artifact_repo.valid_section_id(db, project_id, form.get("section_id")),
        "identifier": identifier,
        "stakeholder_type_id": _stakeholder_type_id(form.get("stakeholder_type_id")),
        "want": form.get("want"),
        "benefit": form.get("benefit"),
        "position": artifact_repo.next_story_position(db, project_id),
    }
    artifact_repo.create_story(db, values)


def update_story(db: Session, story_id: int, form: Mapping[str, Any]) -> str:
    row = artifact_repo.get_story(db, story_id)
    if row is None:
        return "История не найдена"
    identifier = str(form.get("identifier") or "").strip() or row["identifier"] or f"US-{story_id}"
    artifact_repo.update_story(
        db,
        story_id,
        {
            "identifier": identifier,
            "stakeholder_type_id": _stakeholder_type_id(form.get("stakeholder_type_id")),
            "want": form.get("want"),
            "benefit": form.get("benefit"),
        },
    )
    return ""


def delete_story(db: Session, story_id: int) -> None:
    artifact_repo.soft_delete_story(db, story_id)


def create_section(db: Session, project_id: int, name: str) -> str:
    name = name.strip()
    if not name:
        return "Укажите проект и название раздела"
    artifact_repo.create_section(db, project_id, name, artifact_repo.next_section_position(db, project_id))
    return ""


def rename_section(db: Session, section_id: int, name: str) -> str:
    name = name.strip()
    if not name or artifact_repo.get_section(db, section_id) is None:
        return "Раздел не найден или не задано название"
    artifact_repo.rename_section(db, section_id, name)
    return ""


def delete_section(db: Session, section_id: int) -> str:
    if artifact_repo.get_section(db, section_id) is None:
        return "Раздел не найден"
    if artifact_repo.section_has_children(db, section_id) or artifact_repo.section_has_stories(db, section_id):
        return "Раздел не пуст: сначала перенесите или удалите вложенные разделы и истории"
    artifact_repo.soft_delete_section(db, section_id)
    return ""


def reorder(db: Session, project_id: int, data: Mapping[str, Any]) -> None:
    section_ids = {int(section["id"]) for section in artifact_repo.list_sections(db, project_id)}
    for index, section_id in enumerate(data.get("sections") or []):
        parsed = _to_int(section_id)
        if parsed is not None and parsed in section_ids:
            artifact_repo.set_section_position(db, parsed, project_id, index)
    for index, item in enumerate(data.get("stories") or []):
        if not isinstance(item, dict):
            continue
        story_id = _to_int(item.get("id"))
        if story_id is None:
            continue
        section_id = _to_int(item.get("section_id"))
        if section_id is not None and section_id not in section_ids:
            section_id = None
        artifact_repo.set_story_order(db, story_id, project_id, index, section_id)
    artifact_repo.commit(db)
