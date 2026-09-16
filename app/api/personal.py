"""«Мои задачи» и админ-страница задач: HTTP-контроллеры."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin, require_user
from app.presentation import personal_views
from app.presentation.render import render
from app.services import personal_service, task_service

router = APIRouter()


@router.get("/my_tasks", name="my_tasks", dependencies=[Depends(require_user)])
def my_tasks(request: Request, db: Session = Depends(get_db), user: dict = Depends(require_user)):
    items = personal_service.my_tasks(db, user)
    content = personal_views.my_tasks_content(request, items, task_service.status_list(db))
    return render(request, "pages/content.html", db, title="Мои задачи", content=content)


@router.get("/tasks_admin", name="admin_tasks", dependencies=[Depends(require_admin)])
def admin_tasks(request: Request, db: Session = Depends(get_db)):
    tab = personal_service.normalize_tab(request.query_params.get("tab"))
    items, project_employees = personal_service.admin_tasks(db, tab)
    content = personal_views.admin_tasks_content(request, items, task_service.status_list(db), tab, project_employees)
    return render(request, "pages/content.html", db, title="Задачи", content=content)
