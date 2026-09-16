"""Все ORM-модели. Импорт этого модуля регистрирует все таблицы в metadata."""

from app.db.models.artifacts import ProjectArtifact, UserStory, UserStorySection
from app.db.models.interviews import (
    Interview,
    InterviewAudio,
    InterviewQa,
    InterviewTemplate,
    InterviewTemplateQuestion,
    TranscriptSegment,
)
from app.db.models.people import Employee, Stakeholder
from app.db.models.projects import (
    Project,
    ProjectEmployee,
    ProjectStage,
    ProjectStakeholder,
    Requirement,
)
from app.db.models.reference import (
    EmployeeStatus,
    NonfunctionalRequirementType,
    PositionType,
    Priority,
    ProjectStageStatus,
    ProjectStageType,
    RequirementType,
    StakeholderType,
    TaskStatus,
    TaskType,
)
from app.db.models.system import AppUser, AuditLog, ChatMessage, Setting
from app.db.models.work import Comment, Event, Subtask, Task, TaskAssignment

__all__ = [
    "AppUser",
    "AuditLog",
    "ChatMessage",
    "Comment",
    "Employee",
    "EmployeeStatus",
    "Event",
    "Interview",
    "InterviewAudio",
    "InterviewQa",
    "InterviewTemplate",
    "InterviewTemplateQuestion",
    "NonfunctionalRequirementType",
    "PositionType",
    "Priority",
    "Project",
    "ProjectArtifact",
    "ProjectEmployee",
    "ProjectStage",
    "ProjectStageStatus",
    "ProjectStageType",
    "ProjectStakeholder",
    "Requirement",
    "RequirementType",
    "Setting",
    "Stakeholder",
    "StakeholderType",
    "Subtask",
    "Task",
    "TaskAssignment",
    "TaskStatus",
    "TaskType",
    "TranscriptSegment",
    "UserStory",
    "UserStorySection",
]
