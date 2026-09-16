"""Системные таблицы: пользователи, настройки, аудит, чат."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class AppUser(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "app_user"
    __table_args__ = (CheckConstraint("role IN ('admin','user')"),)

    login: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="user", server_default="user")
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employee.id"))
    is_analyst: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=sa_text("CURRENT_TIMESTAMP"))


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_created", "created_at"),
        Index("idx_audit_project", "project_id"),
        Index("idx_audit_user", "user_id"),
    )

    user_id: Mapped[int | None] = mapped_column(Integer)
    user_login: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    project_id: Mapped[int | None] = mapped_column(Integer)
    position_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=sa_text("CURRENT_TIMESTAMP"))


class ChatMessage(IdMixin, Base):
    __tablename__ = "chat_message"

    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))
    author: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=sa_text("CURRENT_TIMESTAMP"))
