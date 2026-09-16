"""Репозиторий пользователей и связанных справочных записей."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.people import Employee
from app.db.models.reference import EmployeeStatus, PositionType
from app.db.models.system import AppUser


def find_by_login(db: Session, login: str, include_deleted: bool = False) -> AppUser | None:
    stmt = select(AppUser).where(func.lower(AppUser.login) == login.lower())
    if not include_deleted:
        stmt = stmt.where(AppUser.is_deleted == 0)
    return db.execute(stmt).scalars().first()


def default_position(db: Session) -> PositionType:
    row = (
        db.execute(
            select(PositionType).where(func.lower(PositionType.name) == "Пользователь", PositionType.is_deleted == 0)
        )
        .scalars()
        .first()
    )
    if row is None:
        row = PositionType(name="Пользователь")
        db.add(row)
        db.flush()
    return row


def default_status(db: Session) -> EmployeeStatus:
    row = (
        db.execute(
            select(EmployeeStatus).where(func.lower(EmployeeStatus.name) == "Работает", EmployeeStatus.is_deleted == 0)
        )
        .scalars()
        .first()
    )
    if row is None:
        row = EmployeeStatus(name="Работает", is_available=1)
        db.add(row)
        db.flush()
    return row


def create_employee(db: Session, last_name: str, first_name: str, middle_name: str) -> Employee:
    employee = Employee(
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
        position_type_id=default_position(db).id,
        status_id=default_status(db).id,
        subordinates_total=0,
        subordinates_available=0,
        is_stackholder=0,
    )
    db.add(employee)
    db.flush()
    return employee


def create_user(db: Session, login: str, password: str, role: str, employee_id: int | None) -> AppUser:
    user = AppUser(login=login, password=password, role=role, employee_id=employee_id)
    db.add(user)
    db.flush()
    return user
