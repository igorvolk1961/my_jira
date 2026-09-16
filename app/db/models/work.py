"""Задачи, подзадачи, назначения, комментарии, события."""

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Task(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "task"

    requirement_id: Mapped[int | None] = mapped_column(ForeignKey("requirement.id", ondelete="SET NULL"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("project_stage.id"))
    task_type_id: Mapped[int | None] = mapped_column(ForeignKey("task_type.id"))
    priority_id: Mapped[int] = mapped_column(ForeignKey("priority.id"), nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date)
    status_id: Mapped[int] = mapped_column(ForeignKey("task_status.id"), nullable=False)


class Subtask(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "subtask"

    parent_task_id: Mapped[int] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    parent_subtask_id: Mapped[int | None] = mapped_column(ForeignKey("subtask.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("project_stage.id"))
    priority_id: Mapped[int] = mapped_column(ForeignKey("priority.id"), nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date)
    status_id: Mapped[int] = mapped_column(ForeignKey("task_status.id"), nullable=False)


class TaskAssignment(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "task_assignment"
    __table_args__ = (
        CheckConstraint("task_kind IN ('task','subtask')"),
        CheckConstraint("share BETWEEN 0 AND 1"),
        UniqueConstraint("task_id", "task_kind", "employee_id"),
    )

    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    task_kind: Mapped[str] = mapped_column(Text, nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employee.id"), nullable=False)
    share: Mapped[float] = mapped_column(Float, nullable=False)
    assigned_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime)


class Comment(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "comment"
    __table_args__ = (CheckConstraint("entity_type IN ('task', 'subtask')"),)

    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    author: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))


class Event(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "event"

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str | None] = mapped_column(Text)
