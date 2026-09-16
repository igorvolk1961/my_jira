"""Главная страница и выбор текущего проекта."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import current_project, get_db
from app.flash import flash
from app.presentation.render import render
from app.security import safe_next
from app.services import dashboard_service, project_service

router = APIRouter()


@router.get("/", name="index")
def index(request: Request, db: Session = Depends(get_db)):
    stats = dashboard_service.dashboard_stats(db)
    projects = project_service.list_projects(db)
    project = current_project(request, db)
    return render(
        request,
        "pages/index.html",
        db,
        title="Главная",
        stats=stats,
        projects=projects,
        current_project=project,
    )


@router.get("/current-project/{id}", name="current_project_set")
def current_project_set(id: int, request: Request, db: Session = Depends(get_db)):
    if not project_service.set_current(db, id):
        flash(request, "Проект не найден", "error")
        return RedirectResponse(str(request.url_for("index")), status_code=302)
    request.session["project_id"] = id
    target = safe_next(request.query_params.get("next"), str(request.url_for("index")))
    return RedirectResponse(target, status_code=302)
