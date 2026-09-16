"""Репозиторий интервью: интервью, вопросы-ответы, аудио, транскрипт, шаблоны."""

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

Row = dict[str, Any]


# ==================== ИНТЕРВЬЮ ====================


def list_interviews(db: Session) -> list[Row]:
    rows = (
        db.execute(
            text(
                """
                SELECT i.*, s.last_name, s.first_name
                FROM interview i JOIN stakeholder s ON i.stakeholder_id=s.id
                WHERE i.is_deleted=0 ORDER BY i.scheduled_at DESC, i.id DESC
                """
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get_interview(db: Session, interview_id: int) -> Row | None:
    row = (
        db.execute(
            text(
                """
                SELECT i.*, s.last_name, s.first_name, s.position
                FROM interview i JOIN stakeholder s ON i.stakeholder_id=s.id
                WHERE i.id=:id AND i.is_deleted=0
                """
            ),
            {"id": interview_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def create_interview(db: Session, stakeholder_id: int, scheduled_at: datetime | None) -> int:
    result = db.execute(
        text("INSERT INTO interview (stakeholder_id, scheduled_at) VALUES (:sid, :scheduled) RETURNING id"),
        {"sid": stakeholder_id, "scheduled": scheduled_at},
    )
    return int(result.scalar_one())


def update_interview(db: Session, interview_id: int, stakeholder_id: int, scheduled_at: datetime | None) -> None:
    db.execute(
        text(
            """
            UPDATE interview SET stakeholder_id=:sid, scheduled_at=:scheduled, updated_at=CURRENT_TIMESTAMP
            WHERE id=:id
            """
        ),
        {"sid": stakeholder_id, "scheduled": scheduled_at, "id": interview_id},
    )


def soft_delete_interview(db: Session, interview_id: int) -> None:
    db.execute(
        text("UPDATE interview SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
        {"id": interview_id},
    )


def list_stakeholder_options(db: Session) -> list[Row]:
    rows = (
        db.execute(text("SELECT id, last_name, first_name FROM stakeholder WHERE is_deleted=0 ORDER BY last_name, id"))
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def list_interview_options(db: Session) -> list[Row]:
    rows = db.execute(text("SELECT id FROM interview WHERE is_deleted=0 ORDER BY id")).mappings().all()
    return [dict(row) for row in rows]


# ==================== ВОПРОСЫ-ОТВЕТЫ ====================


def list_qa(db: Session, interview_id: int) -> list[Row]:
    rows = (
        db.execute(
            text("SELECT * FROM interview_qa WHERE interview_id=:iid AND is_deleted=0 ORDER BY id"),
            {"iid": interview_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get_qa(db: Session, qa_id: int) -> Row | None:
    row = db.execute(text("SELECT * FROM interview_qa WHERE id=:id AND is_deleted=0"), {"id": qa_id}).mappings().first()
    return dict(row) if row else None


def create_qa(db: Session, interview_id: int, question: str, answer: str | None) -> int:
    result = db.execute(
        text(
            "INSERT INTO interview_qa (interview_id, question, answer) VALUES (:iid, :question, :answer) RETURNING id"
        ),
        {"iid": interview_id, "question": question, "answer": answer},
    )
    return int(result.scalar_one())


def update_qa(db: Session, qa_id: int, interview_id: int, question: str, answer: str | None) -> None:
    db.execute(
        text(
            """
            UPDATE interview_qa SET interview_id=:iid, question=:question, answer=:answer,
                   updated_at=CURRENT_TIMESTAMP
            WHERE id=:id
            """
        ),
        {"iid": interview_id, "question": question, "answer": answer, "id": qa_id},
    )


def soft_delete_qa(db: Session, qa_id: int) -> None:
    db.execute(
        text("UPDATE interview_qa SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
        {"id": qa_id},
    )


# ==================== АУДИО ====================


def list_audio(db: Session, interview_id: int) -> list[Row]:
    rows = (
        db.execute(
            text("SELECT * FROM interview_audio WHERE interview_id=:iid AND is_deleted=0 ORDER BY id"),
            {"iid": interview_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get_audio(db: Session, audio_id: int) -> Row | None:
    row = (
        db.execute(text("SELECT * FROM interview_audio WHERE id=:id AND is_deleted=0"), {"id": audio_id})
        .mappings()
        .first()
    )
    return dict(row) if row else None


def get_audio_any(db: Session, audio_id: int) -> Row | None:
    row = db.execute(text("SELECT * FROM interview_audio WHERE id=:id"), {"id": audio_id}).mappings().first()
    return dict(row) if row else None


def get_audio_for_interview(db: Session, audio_id: int, interview_id: int) -> Row | None:
    row = (
        db.execute(
            text("SELECT * FROM interview_audio WHERE id=:id AND interview_id=:iid AND is_deleted=0"),
            {"id": audio_id, "iid": interview_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def get_latest_audio(db: Session, interview_id: int) -> Row | None:
    row = (
        db.execute(
            text("SELECT * FROM interview_audio WHERE interview_id=:iid AND is_deleted=0 ORDER BY id DESC LIMIT 1"),
            {"iid": interview_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def create_audio(
    db: Session,
    interview_id: int,
    filename: str,
    original_name: str | None,
    mime: str | None,
    duration_ms: int | None,
) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO interview_audio (interview_id, filename, original_name, mime, duration_ms)
            VALUES (:iid, :filename, :original_name, :mime, :duration_ms) RETURNING id
            """
        ),
        {
            "iid": interview_id,
            "filename": filename,
            "original_name": original_name,
            "mime": mime,
            "duration_ms": duration_ms,
        },
    )
    return int(result.scalar_one())


def soft_delete_audio(db: Session, audio_id: int) -> None:
    db.execute(text("UPDATE interview_audio SET is_deleted=1 WHERE id=:id"), {"id": audio_id})


# ==================== ТРАНСКРИПТ ====================


def list_segments(db: Session, interview_id: int) -> list[Row]:
    rows = (
        db.execute(
            text("SELECT * FROM transcript_segment WHERE interview_id=:iid AND is_deleted=0 ORDER BY start_ms, id"),
            {"iid": interview_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def create_segment(
    db: Session, interview_id: int, audio_id: int | None, start_ms: int, end_ms: int, text_value: str
) -> None:
    db.execute(
        text(
            """
            INSERT INTO transcript_segment (interview_id, audio_id, start_ms, end_ms, text)
            VALUES (:iid, :aid, :start_ms, :end_ms, :text)
            """
        ),
        {"iid": interview_id, "aid": audio_id, "start_ms": start_ms, "end_ms": end_ms, "text": text_value},
    )


def update_segment(db: Session, segment_id: int, interview_id: int, text_value: str, speaker: str | None) -> None:
    db.execute(
        text(
            """
            UPDATE transcript_segment SET text=:text, speaker=:speaker, updated_at=CURRENT_TIMESTAMP
            WHERE id=:id AND interview_id=:iid
            """
        ),
        {"text": text_value, "speaker": speaker, "id": segment_id, "iid": interview_id},
    )


def soft_delete_segment(db: Session, segment_id: int, interview_id: int) -> None:
    db.execute(
        text(
            "UPDATE transcript_segment SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:id AND interview_id=:iid"
        ),
        {"id": segment_id, "iid": interview_id},
    )


def soft_delete_segments(db: Session, interview_id: int) -> None:
    db.execute(
        text("UPDATE transcript_segment SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE interview_id=:iid"),
        {"iid": interview_id},
    )


def soft_delete_segments_for_audio(db: Session, interview_id: int, audio_id: int) -> None:
    db.execute(
        text(
            """
            UPDATE transcript_segment SET is_deleted=1, updated_at=CURRENT_TIMESTAMP
            WHERE interview_id=:iid AND audio_id=:aid
            """
        ),
        {"iid": interview_id, "aid": audio_id},
    )


# ==================== ШАБЛОНЫ ====================


def list_templates(db: Session) -> list[Row]:
    rows = (
        db.execute(
            text(
                """
                SELECT t.*, (SELECT COUNT(*) FROM interview_template_question q
                             WHERE q.template_id=t.id AND q.is_deleted=0) AS q_count
                FROM interview_template t WHERE t.is_deleted=0 ORDER BY t.name, t.id
                """
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def list_template_options(db: Session) -> list[Row]:
    rows = (
        db.execute(text("SELECT id, name FROM interview_template WHERE is_deleted=0 ORDER BY name, id"))
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get_template(db: Session, template_id: int) -> Row | None:
    row = (
        db.execute(text("SELECT * FROM interview_template WHERE id=:id AND is_deleted=0"), {"id": template_id})
        .mappings()
        .first()
    )
    return dict(row) if row else None


def create_template(db: Session, name: str, description: str | None) -> int:
    result = db.execute(
        text("INSERT INTO interview_template (name, description) VALUES (:name, :description) RETURNING id"),
        {"name": name, "description": description},
    )
    return int(result.scalar_one())


def soft_delete_template(db: Session, template_id: int) -> None:
    db.execute(
        text("UPDATE interview_template SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
        {"id": template_id},
    )
    db.execute(
        text(
            """
            UPDATE interview_template_question SET is_deleted=1, updated_at=CURRENT_TIMESTAMP
            WHERE template_id=:id
            """
        ),
        {"id": template_id},
    )


def list_template_questions(db: Session, template_id: int) -> list[Row]:
    rows = (
        db.execute(
            text(
                """
                SELECT * FROM interview_template_question
                WHERE template_id=:tid AND is_deleted=0 ORDER BY position, id
                """
            ),
            {"tid": template_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get_template_question(db: Session, question_id: int) -> Row | None:
    row = (
        db.execute(
            text("SELECT * FROM interview_template_question WHERE id=:id AND is_deleted=0"),
            {"id": question_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def next_question_position(db: Session, template_id: int) -> int:
    value = db.execute(
        text("SELECT COALESCE(MAX(position), -1) + 1 FROM interview_template_question WHERE template_id=:tid"),
        {"tid": template_id},
    ).scalar_one()
    return int(value or 0)


def create_template_question(db: Session, template_id: int, question: str, answer: str | None, position: int) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO interview_template_question (template_id, question, answer, position)
            VALUES (:tid, :question, :answer, :position) RETURNING id
            """
        ),
        {"tid": template_id, "question": question, "answer": answer, "position": position},
    )
    return int(result.scalar_one())


def update_template_question(db: Session, question_id: int, question: str, answer: str | None) -> None:
    db.execute(
        text(
            """
            UPDATE interview_template_question SET question=:question, answer=:answer, updated_at=CURRENT_TIMESTAMP
            WHERE id=:id
            """
        ),
        {"question": question, "answer": answer, "id": question_id},
    )


def soft_delete_template_question(db: Session, question_id: int) -> None:
    db.execute(
        text("UPDATE interview_template_question SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
        {"id": question_id},
    )
