"""Артефакты системного аналитика и пользовательские истории."""

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class ProjectArtifact(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "project_artifact"
    __table_args__ = (UniqueConstraint("project_id", "artifact_key"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    artifact_key: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))


class UserStorySection(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "user_story_section"

    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("user_story_section.id"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")


class UserStory(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "user_story"

    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("user_story_section.id"))
    identifier: Mapped[str | None] = mapped_column(Text)
    stakeholder_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholder.id"))
    stakeholder_type_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholder_type.id"))
    role: Mapped[str | None] = mapped_column(Text)
    want: Mapped[str | None] = mapped_column(Text)
    benefit: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
