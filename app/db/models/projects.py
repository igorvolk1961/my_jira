"""Проекты, этапы, требования, связи с участниками."""

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Project(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "project"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    main_stakeholder_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholder.id"))
    cost: Mapped[float | None] = mapped_column(Float)
    mvp_deadline: Mapped[date | None] = mapped_column(Date)
    deadline: Mapped[date | None] = mapped_column(Date)
    priority_id: Mapped[int] = mapped_column(ForeignKey("priority.id"), nullable=False)


class Requirement(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "requirement"

    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    stakeholder_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholder.id"))
    requirement_type_id: Mapped[int] = mapped_column(ForeignKey("requirement_type.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority_id: Mapped[int] = mapped_column(ForeignKey("priority.id"), nullable=False)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text)
    nfr_type_id: Mapped[int | None] = mapped_column(ForeignKey("nonfunctional_requirement_type.id"))


class ProjectStage(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "project_stage"

    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    stage_type_id: Mapped[int] = mapped_column(ForeignKey("project_stage_type.id"), nullable=False)
    status_id: Mapped[int] = mapped_column(ForeignKey("project_stage_status.id"), nullable=False)
    planned_end: Mapped[date | None] = mapped_column(Date)


class ProjectStakeholder(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "project_stakeholder"
    __table_args__ = (UniqueConstraint("project_id", "stakeholder_id"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    stakeholder_id: Mapped[int] = mapped_column(ForeignKey("stakeholder.id"), nullable=False)


class ProjectEmployee(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "project_employee"
    __table_args__ = (UniqueConstraint("project_id", "employee_id"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employee.id"), nullable=False)
