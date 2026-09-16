"""Схема БД: baseline-миграция, состав таблиц и идемпотентность заполнения."""

import os
import sqlite3
import tempfile

from app.db.engine import dispose_engine
from app.db.schema import ensure_database

EXPECTED_TABLES = {
    "priority",
    "stakeholder_type",
    "stakeholder",
    "requirement_type",
    "nonfunctional_requirement_type",
    "project",
    "requirement",
    "position_type",
    "employee_status",
    "employee",
    "project_stage_type",
    "project_stage_status",
    "project_stage",
    "task_status",
    "task_type",
    "task",
    "subtask",
    "task_assignment",
    "event",
    "project_stakeholder",
    "project_employee",
    "comment",
    "interview",
    "interview_qa",
    "interview_audio",
    "transcript_segment",
    "app_user",
    "setting",
    "audit_log",
    "chat_message",
    "interview_template",
    "interview_template_question",
    "project_artifact",
    "user_story_section",
    "user_story",
}


def _fresh_db_path() -> str:
    return os.path.join(tempfile.mkdtemp(prefix="upo_schema_"), "check.db")


def test_baseline_creates_all_tables_and_seeds():
    path = _fresh_db_path()
    try:
        ensure_database(path)
        con = sqlite3.connect(path)
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert tables >= EXPECTED_TABLES
        assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0001_baseline"
        assert con.execute("SELECT COUNT(*) FROM priority").fetchone()[0] == 5
        assert con.execute("SELECT COUNT(*) FROM task_type").fetchone()[0] == 6
        assert con.execute("SELECT COUNT(*) FROM interview_template_question").fetchone()[0] == 25
        password = con.execute("SELECT password FROM app_user WHERE login='admin'").fetchone()[0]
        assert password.startswith("pbkdf2_sha256$")
        con.close()
    finally:
        dispose_engine(path)


def test_seed_is_idempotent():
    path = _fresh_db_path()
    try:
        ensure_database(path)
        ensure_database(path)
        con = sqlite3.connect(path)
        assert con.execute("SELECT COUNT(*) FROM task_type").fetchone()[0] == 6
        assert con.execute("SELECT COUNT(*) FROM interview_template_question").fetchone()[0] == 25
        assert con.execute("SELECT COUNT(*) FROM app_user").fetchone()[0] == 1
        con.close()
    finally:
        dispose_engine(path)


def test_legacy_schema_is_reconciled_before_stamp():
    """Старая БД без alembic_version: недостающие колонки/таблицы добавляются, затем stamp."""
    path = _fresh_db_path()
    try:
        ensure_database(path)
        con = sqlite3.connect(path)
        con.execute("ALTER TABLE position_type DROP COLUMN is_analyst")
        con.execute("DROP TABLE nonfunctional_requirement_type")
        con.execute("DROP TABLE alembic_version")
        con.commit()
        con.close()
        dispose_engine(path)

        ensure_database(path)

        con = sqlite3.connect(path)
        columns = [row[1] for row in con.execute("PRAGMA table_info(position_type)")]
        tables = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert "is_analyst" in columns
        assert "nonfunctional_requirement_type" in tables
        assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0001_baseline"
        assert con.execute("SELECT COUNT(*) FROM nonfunctional_requirement_type").fetchone()[0] == 9
        con.close()
    finally:
        dispose_engine(path)
