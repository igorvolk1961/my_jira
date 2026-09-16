"""Интервью: бизнес-логика (интервью, вопросы-ответы, аудио, транскрипт, шаблоны)."""

import contextlib
import os
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import AUDIO_DIR
from app.repositories import interview_repo
from app.services import transcription_service
from app.services.support import to_int

Row = dict[str, Any]
Form = dict[str, Any]

AUDIO_EXTENSION_DEFAULT = ".webm"


# ==================== ОБЩИЕ ПОМОЩНИКИ ====================


def fmt_timecode(ms: int | None) -> str:
    """Миллисекунды → ``ММ:СС`` (как legacy ``fmt_timecode``)."""
    if not ms:
        return "00:00"
    seconds = int(ms) // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _safe_extension(filename: str | None) -> str:
    """Безопасное расширение файла (по мотивам ``secure_filename``)."""
    ext = os.path.splitext(filename or "")[1].lower()
    cleaned = "".join(ch for ch in ext if ch.isalnum() or ch == ".")
    if not cleaned.startswith(".") or len(cleaned) > 10:
        return AUDIO_EXTENSION_DEFAULT
    return cleaned


def audio_path(audio: Row) -> str:
    return os.path.join(AUDIO_DIR, str(audio["filename"]))


# ==================== ИНТЕРВЬЮ ====================


def list_interviews(db: Session) -> list[Row]:
    return interview_repo.list_interviews(db)


def get_interview(db: Session, interview_id: int) -> Row | None:
    return interview_repo.get_interview(db, interview_id)


def create_interview(db: Session, form: Form) -> tuple[str, int | None, int]:
    stakeholder_id = to_int(form.get("stakeholder_id"))
    if not stakeholder_id:
        return "Укажите стейкхолдера", None, 0
    scheduled_at = _parse_datetime(form.get("scheduled_at"))
    new_id = interview_repo.create_interview(db, stakeholder_id, scheduled_at)
    copied = 0
    template_id = to_int(form.get("template_id"))
    if template_id:
        questions = interview_repo.list_template_questions(db, template_id)
        for question in questions:
            interview_repo.create_qa(db, new_id, str(question["question"]), question.get("answer"))
        copied = len(questions)
    db.commit()
    return "", new_id, copied


def update_interview(db: Session, interview_id: int, form: Form) -> str:
    stakeholder_id = to_int(form.get("stakeholder_id"))
    if not stakeholder_id:
        return "Укажите стейкхолдера"
    scheduled_at = _parse_datetime(form.get("scheduled_at"))
    interview_repo.update_interview(db, interview_id, stakeholder_id, scheduled_at)
    db.commit()
    return ""


def delete_interview(db: Session, interview_id: int) -> None:
    interview_repo.soft_delete_interview(db, interview_id)
    db.commit()


# ==================== ВОПРОСЫ-ОТВЕТЫ ====================


def list_qa(db: Session, interview_id: int) -> list[Row]:
    return interview_repo.list_qa(db, interview_id)


def get_qa(db: Session, qa_id: int) -> Row | None:
    return interview_repo.get_qa(db, qa_id)


def create_qa(db: Session, form: Form) -> tuple[str, int | None]:
    interview_id = to_int(form.get("interview_id"))
    question = str(form.get("question") or "").strip()
    if not interview_id:
        return "Укажите интервью", None
    if not question:
        return "Укажите вопрос", None
    answer = str(form.get("answer") or "").strip() or None
    interview_repo.create_qa(db, interview_id, question, answer)
    db.commit()
    return "", interview_id


def update_qa(db: Session, qa_id: int, form: Form) -> tuple[str, int | None]:
    interview_id = to_int(form.get("interview_id"))
    question = str(form.get("question") or "").strip()
    if not interview_id:
        return "Укажите интервью", None
    if not question:
        return "Укажите вопрос", interview_id
    answer = str(form.get("answer") or "").strip() or None
    interview_repo.update_qa(db, qa_id, interview_id, question, answer)
    db.commit()
    return "", interview_id


def delete_qa(db: Session, qa_id: int) -> int | None:
    qa = interview_repo.get_qa(db, qa_id)
    if qa is None:
        return None
    interview_id = int(qa["interview_id"])
    interview_repo.soft_delete_qa(db, qa_id)
    db.commit()
    return interview_id


# ==================== АУДИО ====================


def list_audio(db: Session, interview_id: int) -> list[Row]:
    return interview_repo.list_audio(db, interview_id)


def get_audio(db: Session, audio_id: int) -> Row | None:
    return interview_repo.get_audio(db, audio_id)


def save_audio(
    db: Session,
    interview_id: int,
    content: bytes,
    original_name: str | None,
    mime: str | None,
    duration_ms: int | None,
) -> int:
    extension = _safe_extension(original_name)
    name = f"interview_{interview_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{extension}"
    os.makedirs(AUDIO_DIR, exist_ok=True)
    with open(os.path.join(AUDIO_DIR, name), "wb") as stream:
        stream.write(content)
    audio_id = interview_repo.create_audio(db, interview_id, name, original_name, mime, duration_ms)
    db.commit()
    return audio_id


def delete_audio(db: Session, audio_id: int) -> int | None:
    audio = interview_repo.get_audio_any(db, audio_id)
    if audio is None:
        return None
    interview_id = int(audio["interview_id"])
    interview_repo.soft_delete_audio(db, audio_id)
    db.commit()
    with contextlib.suppress(OSError):
        os.remove(audio_path(audio))
    return interview_id


def select_transcription_audio(db: Session, interview_id: int, raw_audio_id: Any) -> Row | None:
    audio_id = to_int(raw_audio_id)
    if audio_id:
        return interview_repo.get_audio_for_interview(db, audio_id, interview_id)
    return interview_repo.get_latest_audio(db, interview_id)


# ==================== ТРАНСКРИПТ ====================


def list_segments(db: Session, interview_id: int) -> list[Row]:
    return interview_repo.list_segments(db, interview_id)


def save_transcript_form(db: Session, interview_id: int, fields: Form) -> int:
    saved = 0
    for key, value in fields.items():
        if not key.startswith("text_"):
            continue
        segment_id = to_int(key[len("text_") :])
        if segment_id is None:
            continue
        speaker = fields.get(f"speaker_{segment_id}")
        speaker_text = str(speaker) if speaker is not None else ""
        interview_repo.update_segment(db, segment_id, interview_id, str(value), speaker_text or None)
        saved += 1
    db.commit()
    return saved


def delete_segment(db: Session, interview_id: int, segment_id: int) -> None:
    interview_repo.soft_delete_segment(db, segment_id, interview_id)
    db.commit()


def clear_segments(db: Session, interview_id: int) -> None:
    interview_repo.soft_delete_segments(db, interview_id)
    db.commit()


def replace_segments(db: Session, interview_id: int, audio_id: int, segments: list[dict[str, Any]]) -> int:
    interview_repo.soft_delete_segments_for_audio(db, interview_id, audio_id)
    for segment in segments:
        interview_repo.create_segment(
            db,
            interview_id,
            audio_id,
            int(segment.get("start_ms") or 0),
            int(segment.get("end_ms") or 0),
            str(segment.get("text") or ""),
        )
    db.commit()
    return len(segments)


def transcribe_audio(path: str) -> list[dict[str, Any]]:
    return transcription_service.transcribe(path)


def build_export_markdown(db: Session, interview_id: int) -> tuple[str, str] | None:
    interview = interview_repo.get_interview(db, interview_id)
    if interview is None:
        return None
    qas = interview_repo.list_qa(db, interview_id)
    segments = interview_repo.list_segments(db, interview_id)
    lines = [f"# Интервью #{interview_id}", ""]
    lines.append(f"- **Стейкхолдер:** {interview['last_name']} {interview['first_name']}")
    if interview.get("position"):
        lines.append(f"- **Должность:** {interview['position']}")
    lines.append(f"- **Дата и время:** {interview['scheduled_at'] or '—'}")
    if qas:
        lines += ["", "## Вопросы и ответы", ""]
        for index, qa in enumerate(qas, 1):
            lines += [
                f"### Вопрос {index}",
                "",
                f"**Вопрос:** {qa['question']}",
                "",
                f"**Ответ:** {qa['answer'] or '_(нет ответа)_'}",
                "",
            ]
    if segments:
        lines += ["", "## Транскрипт", ""]
        for segment in segments:
            who = f" **{segment['speaker']}:**" if segment["speaker"] else ""
            lines.append(f"- `[{fmt_timecode(segment['start_ms'])}]`{who} {segment['text']}")
        lines.append("")
    return f"interview_{interview_id}.md", "\n".join(lines)


# ==================== ШАБЛОНЫ ИНТЕРВЬЮ ====================


def list_templates(db: Session) -> list[Row]:
    return interview_repo.list_templates(db)


def get_template(db: Session, template_id: int) -> Row | None:
    return interview_repo.get_template(db, template_id)


def create_template(db: Session, form: Form) -> tuple[str, int | None]:
    name = str(form.get("name") or "").strip()
    if not name:
        return "Название шаблона обязательно", None
    description = str(form.get("description") or "").strip() or None
    template_id = interview_repo.create_template(db, name, description)
    db.commit()
    return "", template_id


def delete_template(db: Session, template_id: int) -> None:
    interview_repo.soft_delete_template(db, template_id)
    db.commit()


def list_template_questions(db: Session, template_id: int) -> list[Row]:
    return interview_repo.list_template_questions(db, template_id)


def get_template_question(db: Session, question_id: int) -> Row | None:
    return interview_repo.get_template_question(db, question_id)


def create_template_question(db: Session, template_id: int, form: Form) -> str:
    question = str(form.get("question") or "").strip()
    if not question:
        return "Укажите вопрос"
    answer = str(form.get("answer") or "").strip() or None
    position = interview_repo.next_question_position(db, template_id)
    interview_repo.create_template_question(db, template_id, question, answer, position)
    db.commit()
    return ""


def update_template_question(db: Session, question_id: int, form: Form) -> tuple[str, int | None]:
    question = str(form.get("question") or "").strip()
    if not question:
        return "Укажите вопрос", None
    existing = interview_repo.get_template_question(db, question_id)
    template_id = int(existing["template_id"]) if existing and existing.get("template_id") else None
    answer = str(form.get("answer") or "").strip() or None
    interview_repo.update_template_question(db, question_id, question, answer)
    db.commit()
    return "", template_id


def delete_template_question(db: Session, question_id: int) -> int | None:
    question = interview_repo.get_template_question(db, question_id)
    if question is None:
        return None
    template_id = int(question["template_id"]) if question.get("template_id") else None
    interview_repo.soft_delete_template_question(db, question_id)
    db.commit()
    return template_id


def save_interview_as_template(db: Session, interview_id: int, form: Form) -> tuple[str, int | None]:
    questions = interview_repo.list_qa(db, interview_id)
    name = str(form.get("name") or "").strip() or f"Шаблон по интервью #{interview_id}"
    description = str(form.get("description") or "").strip() or None
    template_id = interview_repo.create_template(db, name, description)
    for position, qa in enumerate(questions):
        interview_repo.create_template_question(db, template_id, str(qa["question"]), None, position)
    db.commit()
    return "", template_id


def stakeholder_options(db: Session) -> list[Row]:
    return interview_repo.list_stakeholder_options(db)


def template_options(db: Session) -> list[Row]:
    return interview_repo.list_template_options(db)


def interview_options(db: Session) -> list[Row]:
    return interview_repo.list_interview_options(db)
