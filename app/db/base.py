"""Базовый класс ORM и общие миксины."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class TimestampMixin:
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class SoftDeleteMixin:
    is_deleted: Mapped[int | None] = mapped_column(Integer, default=0, server_default=text("0"))
