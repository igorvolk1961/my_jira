"""Универсальный репозиторий справочников (CRUD + мягкое удаление)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base


def list_active[T: Base](db: Session, model: type[T]) -> list[T]:
    stmt = select(model).where(model.is_deleted == 0).order_by(model.id)  # type: ignore[attr-defined]
    return list(db.execute(stmt).scalars().all())


def get[T: Base](db: Session, model: type[T], item_id: int) -> T | None:
    return db.get(model, item_id)


def create[T: Base](db: Session, model: type[T], values: dict[str, Any]) -> T:
    item = model(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update[T: Base](db: Session, item: T, values: dict[str, Any]) -> T:
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    return item


def soft_delete[T: Base](db: Session, item: T) -> None:
    item.is_deleted = 1  # type: ignore[attr-defined]
    db.commit()
