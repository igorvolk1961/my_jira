"""Люди: сотрудники и стейкхолдеры."""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Employee(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "employee"

    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    middle_name: Mapped[str | None] = mapped_column(Text)
    position_type_id: Mapped[int] = mapped_column(ForeignKey("position_type.id"), nullable=False)
    status_id: Mapped[int] = mapped_column(ForeignKey("employee_status.id"), nullable=False)
    subordinates_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    subordinates_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_stackholder: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class Stakeholder(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "stakeholder"
    __table_args__ = (CheckConstraint("priority BETWEEN 1 AND 5"),)

    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    middle_name: Mapped[str | None] = mapped_column(Text)
    type_id: Mapped[int] = mapped_column(ForeignKey("stakeholder_type.id"), nullable=False)
    position: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employee.id"))
