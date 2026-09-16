"""Реестр контроллеров (роутеров)."""

from fastapi import APIRouter, Depends

from app.api import (
    artifacts,
    assignments,
    audit,
    auth,
    chat,
    comments,
    database,
    employees,
    events,
    interviews,
    main,
    personal,
    projects,
    reference,
    reports,
    requirements,
    settings,
    stages,
    stakeholders,
    tasks,
)
from app.audit import audit_dependency

api_router = APIRouter(dependencies=[Depends(audit_dependency)])
api_router.include_router(main.router)
api_router.include_router(auth.router)
api_router.include_router(reference.router)
api_router.include_router(stakeholders.router)
api_router.include_router(employees.router)
api_router.include_router(projects.router)
api_router.include_router(requirements.router)
api_router.include_router(stages.router)
api_router.include_router(tasks.router)
api_router.include_router(assignments.router)
api_router.include_router(events.router)
api_router.include_router(interviews.router)
api_router.include_router(artifacts.router)
api_router.include_router(comments.router)
api_router.include_router(reports.router)
api_router.include_router(audit.router)
api_router.include_router(personal.router)
api_router.include_router(database.router)
api_router.include_router(chat.router)
api_router.include_router(settings.router)
