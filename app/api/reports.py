"""Отчёты: HTTP-контроллеры (анонимный доступ)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.presentation import report_views
from app.presentation.render import render
from app.services import report_service

router = APIRouter()


@router.get("/reports/projects", name="report_projects")
def report_projects(request: Request, db: Session = Depends(get_db)):
    cards, tables = report_views.projects(request, report_service.projects(db))
    return render(request, "pages/report_page.html", db, title="Отчёт: Проекты", cards=cards, tables=tables)


@router.get("/reports/stakeholders", name="report_stakeholders")
def report_stakeholders(request: Request, db: Session = Depends(get_db)):
    cards, tables = report_views.stakeholders(request, report_service.stakeholders(db))
    return render(request, "pages/report_page.html", db, title="Отчёт: Стейкхолдеры", cards=cards, tables=tables)


@router.get("/reports/employees", name="report_employees")
def report_employees(request: Request, db: Session = Depends(get_db)):
    cards, tables = report_views.employees(request, report_service.employees(db))
    return render(request, "pages/report_page.html", db, title="Отчёт: Сотрудники", cards=cards, tables=tables)


@router.get("/reports/requirements", name="report_requirements")
def report_requirements(request: Request, db: Session = Depends(get_db)):
    cards, tables = report_views.requirements(request, report_service.requirements(db))
    return render(request, "pages/report_page.html", db, title="Отчёт: Требования", cards=cards, tables=tables)


@router.get("/reports/stages", name="report_stages")
def report_stages(request: Request, db: Session = Depends(get_db)):
    cards, tables = report_views.stages(request, report_service.stages(db))
    return render(request, "pages/report_page.html", db, title="Отчёт: Этапы", cards=cards, tables=tables)


@router.get("/reports/tasks", name="report_tasks")
def report_tasks(request: Request, db: Session = Depends(get_db)):
    cards, tables = report_views.tasks(request, report_service.tasks(db))
    return render(request, "pages/report_page.html", db, title="Отчёт: Задачи", cards=cards, tables=tables)


@router.get("/reports/subtasks", name="report_subtasks")
def report_subtasks(request: Request, db: Session = Depends(get_db)):
    cards, tables = report_views.subtasks(request, report_service.subtasks(db))
    return render(request, "pages/report_page.html", db, title="Отчёт: Подзадачи", cards=cards, tables=tables)


@router.get("/reports/assignments", name="report_assignments")
def report_assignments(request: Request, db: Session = Depends(get_db)):
    cards, tables = report_views.assignments(request, report_service.assignments(db))
    return render(request, "pages/report_page.html", db, title="Отчёт: Назначения", cards=cards, tables=tables)


@router.get("/reports/events", name="report_events")
def report_events(request: Request, db: Session = Depends(get_db)):
    cards, tables = report_views.events(request, report_service.events(db))
    return render(request, "pages/report_page.html", db, title="Отчёт: События", cards=cards, tables=tables)
