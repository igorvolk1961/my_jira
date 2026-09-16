"""Справочники: конфигурация ресурсов и бизнес-операции CRUD."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.base import Base
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
from app.repositories import reference_repo


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    type: str = "text"
    required: bool = False


@dataclass(frozen=True)
class Resource:
    key: str
    model: type[Base]
    title: str
    base_path: str
    list_name: str
    create_name: str
    edit_name: str
    delete_name: str
    fields: tuple[Field, ...]
    columns: tuple[str, ...]


RESOURCES: dict[str, Resource] = {
    "priority": Resource(
        "priority",
        Priority,
        "Приоритеты",
        "/priorities",
        "priorities_list",
        "priority_create",
        "priority_edit",
        "priority_delete",
        (Field("name", "Название", required=True), Field("weight", "Вес (1-5)", "number", True)),
        ("id", "name", "weight"),
    ),
    "stakeholder_type": Resource(
        "stakeholder_type",
        StakeholderType,
        "Типы стейкхолдеров",
        "/stakeholder_types",
        "stakeholder_types_list",
        "stakeholder_type_create",
        "stakeholder_type_edit",
        "stakeholder_type_delete",
        (
            Field("name", "Название", required=True),
            Field("influence_priority", "Влияние (1-5)", "number", True),
            Field("interest_priority", "Интерес (1-5)", "number", True),
        ),
        ("id", "name", "influence_priority", "interest_priority"),
    ),
    "requirement_type": Resource(
        "requirement_type",
        RequirementType,
        "Типы требований",
        "/requirement_types",
        "requirement_types_list",
        "requirement_type_create",
        "requirement_type_edit",
        "requirement_type_delete",
        (Field("name", "Название", required=True),),
        ("id", "name"),
    ),
    "nonfunctional_requirement_type": Resource(
        "nonfunctional_requirement_type",
        NonfunctionalRequirementType,
        "Типы нефункциональных требований",
        "/nonfunctional_requirement_types",
        "nonfunctional_requirement_types_list",
        "nonfunctional_requirement_type_create",
        "nonfunctional_requirement_type_edit",
        "nonfunctional_requirement_type_delete",
        (Field("name", "Название", required=True),),
        ("id", "name"),
    ),
    "position_type": Resource(
        "position_type",
        PositionType,
        "Типы должностей",
        "/position_types",
        "position_types_list",
        "position_type_create",
        "position_type_edit",
        "position_type_delete",
        (Field("name", "Название", required=True), Field("is_analyst", "Системный аналитик", "checkbox")),
        ("id", "name", "is_analyst"),
    ),
    "employee_status": Resource(
        "employee_status",
        EmployeeStatus,
        "Статусы сотрудников",
        "/employee_statuses",
        "employee_statuses_list",
        "employee_status_create",
        "employee_status_edit",
        "employee_status_delete",
        (Field("name", "Название", required=True), Field("is_available", "Доступен", "checkbox")),
        ("id", "name", "is_available"),
    ),
    "stage_type": Resource(
        "stage_type",
        ProjectStageType,
        "Типы этапов",
        "/stage_types",
        "stage_types_list",
        "stage_type_create",
        "stage_type_edit",
        "stage_type_delete",
        (Field("name", "Название", required=True), Field("sort_order", "Порядок", "number")),
        ("id", "name", "sort_order"),
    ),
    "stage_status": Resource(
        "stage_status",
        ProjectStageStatus,
        "Статусы этапов",
        "/stage_statuses",
        "stage_statuses_list",
        "stage_status_create",
        "stage_status_edit",
        "stage_status_delete",
        (Field("name", "Название", required=True), Field("color", "Цвет")),
        ("id", "name", "color"),
    ),
    "task_status": Resource(
        "task_status",
        TaskStatus,
        "Статусы задач",
        "/task_statuses",
        "task_statuses_list",
        "task_status_create",
        "task_status_edit",
        "task_status_delete",
        (Field("name", "Название", required=True), Field("color", "Цвет")),
        ("id", "name", "color"),
    ),
    "task_type": Resource(
        "task_type",
        TaskType,
        "Типы задач",
        "/task_types",
        "task_types_list",
        "task_type_create",
        "task_type_edit",
        "task_type_delete",
        (Field("name", "Название", required=True),),
        ("id", "name"),
    ),
}


def list_items(db: Session, resource: Resource) -> list[Base]:
    return reference_repo.list_active(db, resource.model)


def get_item(db: Session, resource: Resource, item_id: int) -> Base | None:
    return reference_repo.get(db, resource.model, item_id)


def build_values(resource: Resource, form: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Преобразует данные формы в значения модели. Возвращает (values, ошибка)."""
    values: dict[str, Any] = {}
    for field in resource.fields:
        raw = form.get(field.name)
        if field.type == "checkbox":
            values[field.name] = 1 if raw else 0
            continue
        text = (str(raw) if raw is not None else "").strip()
        if field.required and not text:
            return {}, f"Поле «{field.label}» обязательно"
        if field.type == "number":
            if text == "":
                values[field.name] = None
            else:
                try:
                    values[field.name] = int(text)
                except ValueError:
                    return {}, f"Поле «{field.label}» должно быть числом"
        else:
            values[field.name] = text or None
    return values, ""


def create_item(db: Session, resource: Resource, form: dict[str, Any]) -> str:
    values, error = build_values(resource, form)
    if error:
        return error
    reference_repo.create(db, resource.model, values)
    return ""


def update_item(db: Session, resource: Resource, item: Base, form: dict[str, Any]) -> str:
    values, error = build_values(resource, form)
    if error:
        return error
    reference_repo.update(db, item, values)
    return ""


def delete_item(db: Session, item: Base) -> None:
    reference_repo.soft_delete(db, item)
