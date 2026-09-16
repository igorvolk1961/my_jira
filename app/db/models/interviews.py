"""Интервью: интервью, вопросы-ответы, аудио, транскрипт, шаблоны."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Interview(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "interview"

    stakeholder_id: Mapped[int] = mapped_column(ForeignKey("stakeholder.id"), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)


class InterviewQa(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "interview_qa"

    interview_id: Mapped[int] = mapped_column(ForeignKey("interview.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)


class InterviewAudio(IdMixin, SoftDeleteMixin, Base):
    __tablename__ = "interview_audio"

    interview_id: Mapped[int] = mapped_column(ForeignKey("interview.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str | None] = mapped_column(Text)
    mime: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class TranscriptSegment(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "transcript_segment"
    __table_args__ = (Index("idx_seg_interview", "interview_id", "start_ms"),)

    interview_id: Mapped[int] = mapped_column(ForeignKey("interview.id", ondelete="CASCADE"), nullable=False)
    audio_id: Mapped[int | None] = mapped_column(ForeignKey("interview_audio.id"))
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    speaker: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class InterviewTemplate(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "interview_template"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class InterviewTemplateQuestion(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "interview_template_question"

    template_id: Mapped[int | None] = mapped_column(ForeignKey("interview_template.id"))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
