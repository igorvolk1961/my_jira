"""Аудит действий: глобальная зависимость вместо Flask before_request.

Переносит логику `_endpoint_entity_type/_audit_entity_id/_audit_project_id/_audit_details`
из легаси (app_core.py).
"""

from typing import Any

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.dependencies import current_user, get_db

ADMIN_WRITE_ENDPOINTS = {
    "priority_create",
    "priority_edit",
    "priority_delete",
    "stakeholder_type_create",
    "stakeholder_type_edit",
    "stakeholder_type_delete",
    "requirement_type_create",
    "requirement_type_edit",
    "requirement_type_delete",
    "nonfunctional_requirement_type_create",
    "nonfunctional_requirement_type_edit",
    "nonfunctional_requirement_type_delete",
    "position_type_create",
    "position_type_edit",
    "position_type_delete",
    "employee_status_create",
    "employee_status_edit",
    "employee_status_delete",
    "stage_type_create",
    "stage_type_edit",
    "stage_type_delete",
    "stage_status_create",
    "stage_status_edit",
    "stage_status_delete",
    "task_status_create",
    "task_status_edit",
    "task_status_delete",
    "task_type_create",
    "task_type_edit",
    "task_type_delete",
    "stakeholder_create",
    "stakeholder_edit",
    "stakeholder_delete",
    "employee_create",
    "employee_edit",
    "employee_delete",
    "employee_role_change",
    "project_create",
    "project_edit",
    "project_delete",
    "project_add_stakeholder",
    "project_remove_stakeholder",
    "project_add_employee",
    "project_remove_employee",
    "project_stage_create",
    "project_stage_edit",
    "project_stage_delete",
    "task_create",
    "task_edit",
    "task_delete",
    "task_assignment_edit",
    "task_assignment_delete",
    "event_create",
    "event_edit",
    "event_delete",
    "interview_create",
    "interview_edit",
    "interview_delete",
    "interview_qa_create",
    "interview_qa_edit",
    "interview_qa_delete",
    "interview_template_create",
    "interview_template_delete",
    "interview_template_question_create",
    "interview_template_question_edit",
    "interview_template_question_delete",
    "interview_save_as_template",
    "interview_audio_upload",
    "interview_audio_delete",
    "interview_transcribe",
    "transcript_edit",
    "transcript_segments_save",
    "transcript_clear",
    "transcript_segment_delete",
    "database_create",
    "database_delete",
    "database_use",
    "database_copy",
    "audit_index",
    "settings_index",
    "admin_tasks",
}

USER_WRITE_ENDPOINTS = {
    "subtask_create",
    "subtask_edit",
    "subtask_delete",
    "task_status_change",
    "subtask_status_change",
    "comment_create",
    "comment_delete",
    "task_assignment_create",
    "chat_post",
    "my_tasks",
}

ANALYST_WRITE_ENDPOINTS = {
    "requirement_create",
    "requirement_edit",
    "requirement_delete",
    "artifact_edit",
    "artifact_clear",
    "user_story_create",
    "user_story_edit",
    "user_story_delete",
    "user_story_section_create",
    "user_story_section_edit",
    "user_story_section_delete",
    "user_story_reorder",
}

WRITE_ENDPOINTS = ADMIN_WRITE_ENDPOINTS | USER_WRITE_ENDPOINTS | ANALYST_WRITE_ENDPOINTS
PUBLIC_ENDPOINTS = {"login", "register", "logout"}

GET_MUTATION_ENDPOINTS = {
    "database_use",
    "database_delete",
    "logout",
    "project_remove_stakeholder",
    "project_remove_employee",
    "interview_audio_upload",
    "interview_audio_delete",
    "interview_transcribe",
    "interview_template_delete",
    "interview_template_question_delete",
    "transcript_edit",
    "transcript_segments_save",
    "transcript_clear",
    "transcript_segment_delete",
    "comment_delete",
    "subtask_delete",
    "task_assignment_delete",
    "task_delete",
    "employee_delete",
    "stakeholder_delete",
    "project_delete",
    "requirement_delete",
    "artifact_clear",
    "user_story_delete",
    "user_story_section_delete",
    "project_stage_delete",
    "event_delete",
    "interview_delete",
    "interview_qa_delete",
    "employee_status_delete",
    "position_type_delete",
    "priority_delete",
    "stakeholder_type_delete",
    "requirement_type_delete",
    "nonfunctional_requirement_type_delete",
    "stage_type_delete",
    "stage_status_delete",
    "task_status_delete",
    "task_type_delete",
}


def _audit_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def endpoint_entity_type(endpoint: str | None, form: dict[str, Any]) -> str | None:
    e = endpoint or ""
    if e in ("task_status_change", "subtask_status_change"):
        return "task" if e == "task_status_change" else "subtask"
    if e == "task_assignment_create":
        kind = form.get("task_kind")
        return kind if kind in ("task", "subtask") else "assignment"
    if e.startswith("task_assignment"):
        return "assignment"
    if e.startswith("task_status") or e.startswith("task_type"):
        return "reference"
    if e.startswith("task_"):
        return "task"
    if e.startswith("subtask_"):
        return "subtask"
    if e.startswith("project_stage"):
        return "stage"
    if e.startswith("project_"):
        return "project"
    if e.startswith("requirement"):
        return "requirement"
    if e.startswith("stakeholder_type"):
        return "reference"
    if e.startswith("stakeholder"):
        return "stakeholder"
    if e.startswith("employee_status"):
        return "reference"
    if e.startswith("employee"):
        return "employee"
    if e.startswith("comment"):
        return "comment"
    if e.startswith("chat"):
        return "chat"
    if e.startswith("interview") or e.startswith("transcript"):
        return "interview"
    if e.startswith("event"):
        return "event"
    if e.startswith("database"):
        return "database"
    if e.startswith("priority"):
        return "reference"
    if e.startswith("position_type"):
        return "reference"
    if e.startswith("stage_"):
        return "reference"
    if e.startswith("setting"):
        return "setting"
    if e.startswith("my_tasks"):
        return "user"
    return None


def _audit_entity_id(path_params: dict[str, Any], form: dict[str, Any]) -> int | None:
    for value in (path_params or {}).values():
        parsed = _audit_int(value)
        if parsed is not None:
            return parsed
    for key in ("entity_id", "task_id", "parent_task_id", "parent_subtask_id", "id", "project_id", "employee_id"):
        parsed = _audit_int(form.get(key))
        if parsed is not None:
            return parsed
    return None


def _entity_project_id(db: Session, etype: str, eid: int) -> int | None:
    if etype == "task":
        row = db.execute(
            text(
                "SELECT COALESCE(ps.project_id, r.project_id) pid FROM task t"
                " LEFT JOIN project_stage ps ON t.stage_id=ps.id"
                " LEFT JOIN requirement r ON t.requirement_id=r.id"
                " WHERE t.id=:eid AND t.is_deleted=0"
            ),
            {"eid": eid},
        ).first()
    else:
        row = db.execute(
            text(
                "SELECT COALESCE(ps.project_id, r.project_id) pid FROM subtask s"
                " JOIN task t ON s.parent_task_id=t.id"
                " LEFT JOIN project_stage ps ON t.stage_id=ps.id"
                " LEFT JOIN requirement r ON t.requirement_id=r.id"
                " WHERE s.id=:eid AND s.is_deleted=0"
            ),
            {"eid": eid},
        ).first()
    return row[0] if row and row[0] else None


def _audit_project_id(db: Session, etype: str | None, eid: int | None, form: dict[str, Any]) -> int | None:
    try:
        if etype == "project" and eid:
            return eid
        if etype in ("task", "subtask") and eid:
            return _entity_project_id(db, etype, eid)
        if etype == "comment":
            ce = form.get("entity_type")
            ci = _audit_int(form.get("entity_id"))
            if ce and ci:
                return _entity_project_id(db, ce, ci)
        if etype == "assignment" and eid:
            row = db.execute(text("SELECT task_kind, task_id FROM task_assignment WHERE id=:eid"), {"eid": eid}).first()
            if row:
                return _entity_project_id(db, row[0], row[1])
        if etype == "requirement" and eid:
            row = db.execute(text("SELECT project_id FROM requirement WHERE id=:eid"), {"eid": eid}).first()
            return row[0] if row else None
        if etype == "stage" and eid:
            row = db.execute(text("SELECT project_id FROM project_stage WHERE id=:eid"), {"eid": eid}).first()
            return row[0] if row else None
    except SQLAlchemyError:
        return None
    return None


def _audit_details(form: dict[str, Any], method: str) -> str | None:
    if method != "POST":
        return None
    parts = []
    for key, value in form.items():
        text_value = "***" if key == "password" else str(value)
        if len(text_value) > 60:
            text_value = text_value[:60] + "…"
        parts.append(f"{key}={text_value}")
    out = "; ".join(parts)
    return out[:300] if out else None


def log_action(
    db: Session,
    action: str,
    user: dict[str, Any] | None = None,
    form: dict[str, Any] | None = None,
    path_params: dict[str, Any] | None = None,
    method: str = "POST",
    entity_type: str | None = None,
    entity_id: int | None = None,
    project_id: int | None = None,
    details: str | None = None,
) -> None:
    form = form or {}
    path_params = path_params or {}
    try:
        if entity_type is None:
            entity_type = endpoint_entity_type(action, form)
        if entity_id is None:
            entity_id = _audit_entity_id(path_params, form)
        if project_id is None:
            project_id = _audit_project_id(db, entity_type, entity_id, form)
        if details is None:
            details = _audit_details(form, method)
        user_login = user["login"] if user else (form.get("login") if method == "POST" else None)
        db.execute(
            text(
                "INSERT INTO audit_log (user_id, user_login, action, entity_type, entity_id,"
                " project_id, position_id, details)"
                " VALUES (:user_id, :user_login, :action, :entity_type, :entity_id,"
                " :project_id, :position_id, :details)"
            ),
            {
                "user_id": user["id"] if user else None,
                "user_login": user_login,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "project_id": project_id,
                "position_id": user["position_id"] if user else None,
                "details": details,
            },
        )
        db.commit()
    except SQLAlchemyError:
        pass


async def audit_dependency(
    request: Request,
    db: Session = Depends(get_db),
    user: dict[str, Any] | None = Depends(current_user),
) -> None:
    route = request.scope.get("route")
    endpoint = getattr(route, "name", None)
    if not endpoint:
        return
    if endpoint not in WRITE_ENDPOINTS and endpoint not in PUBLIC_ENDPOINTS:
        return
    if request.method != "POST" and endpoint not in GET_MUTATION_ENDPOINTS:
        return
    if endpoint not in PUBLIC_ENDPOINTS and user is None:
        return
    form: dict[str, Any] = {}
    try:
        if request.method == "POST":
            form = dict(await request.form())
    except Exception:  # noqa: BLE001 - аудит не должен ломать запрос
        form = {}
    await run_in_threadpool(
        log_action,
        db,
        endpoint,
        user,
        form,
        dict(request.path_params),
        request.method,
    )
