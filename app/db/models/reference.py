"""Справочники: приоритеты, типы, статусы."""

from sqlalchemy import CheckConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Priority(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "priority"
    __table_args__ = (CheckConstraint("weight BETWEEN 1 AND 5"),)

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)


class StakeholderType(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "stakeholder_type"
    __table_args__ = (
        CheckConstraint("influence_priority BETWEEN 1 AND 5"),
        CheckConstraint("interest_priority BETWEEN 1 AND 5"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    influence_priority: Mapped[int] = mapped_column(Integer, nullable=False)
    interest_priority: Mapped[int] = mapped_column(Integer, nullable=False)


class RequirementType(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "requirement_type"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class NonfunctionalRequirementType(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "nonfunctional_requirement_type"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class PositionType(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "position_type"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    is_analyst: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class EmployeeStatus(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "employee_status"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    is_available: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ProjectStageType(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "project_stage_type"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    sort_order: Mapped[int | None] = mapped_column(Integer)


class ProjectStageStatus(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "project_stage_status"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(Text)


class TaskStatus(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "task_status"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(Text)


class TaskType(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "task_type"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
