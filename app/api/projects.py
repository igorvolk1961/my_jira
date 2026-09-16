"""Проекты: HTTP-контроллеры."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import current_user, get_db, require_admin
from app.flash import flash
from app.presentation import project_views
from app.presentation.capabilities import is_admin
from app.presentation.render import render
from app.services import project_service, requirement_service, stage_service

router = APIRouter()


def _target(request: Request, name: str, **params: object) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return str(request.url_for("index"))


def _as_int(value: object) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


@router.get("/projects", name="projects_list")
def projects_list(request: Request, db: Session = Depends(get_db)):
    projects = project_service.list_for_table(db)
    user = current_user(request, db)
    return render(
        request,
        "pages/list.html",
        db,
        title="Проекты",
        table=project_views.projects_table(request, projects),
        add_url=_target(request, "project_create") if is_admin(user) else None,
        add_label="+ Добавить проект",
    )


@router.api_route(
    "/projects/create", methods=["GET", "POST"], name="project_create", dependencies=[Depends(require_admin)]
)
async def project_create(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error = project_service.create(db, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Проект создан", "success")
            return RedirectResponse(_target(request, "projects_list"), status_code=302)
    options = project_service.form_options(db)
    return render(
        request,
        "pages/form.html",
        db,
        title="Новый проект",
        action=_target(request, "project_create"),
        fields=project_views.project_form_fields(options),
        submit_label="Создать",
        back_url=_target(request, "projects_list"),
    )


@router.api_route(
    "/projects/edit/{id}", methods=["GET", "POST"], name="project_edit", dependencies=[Depends(require_admin)]
)
async def project_edit(id: int, request: Request, db: Session = Depends(get_db)):
    project = project_service.get_detail(db, id)
    if project is None:
        flash(request, "Проект не найден", "error")
        return RedirectResponse(_target(request, "projects_list"), status_code=302)
    if request.method == "POST":
        form = dict(await request.form())
        error = project_service.update(db, id, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Проект обновлён", "success")
            return RedirectResponse(_target(request, "projects_list"), status_code=302)
    options = project_service.form_options(db)
    return render(
        request,
        "pages/form.html",
        db,
        title="Редактировать проект",
        action=_target(request, "project_edit", id=id),
        fields=project_views.project_form_fields(options, project),
        back_url=_target(request, "projects_list"),
    )


@router.get("/projects/delete/{id}", name="project_delete", dependencies=[Depends(require_admin)])
def project_delete(id: int, request: Request, db: Session = Depends(get_db)):
    project_service.delete(db, id)
    flash(request, "Проект удалён", "success")
    return RedirectResponse(_target(request, "projects_list"), status_code=302)


@router.post("/projects/{id}/add_stakeholder", name="project_add_stakeholder", dependencies=[Depends(require_admin)])
async def project_add_stakeholder(id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    stakeholder_id = _as_int(form.get("stakeholder_id"))
    if project_service.add_stakeholder(db, id, stakeholder_id):
        flash(request, "Стейкхолдер добавлен к проекту", "success")
    else:
        flash(request, "Стейкхолдер уже в проекте", "warning")
    return RedirectResponse(_target(request, "project_detail", id=id) + "?tab=stk", status_code=302)


@router.get(
    "/projects/{id}/remove_stakeholder/{stakeholder_id}",
    name="project_remove_stakeholder",
    dependencies=[Depends(require_admin)],
)
def project_remove_stakeholder(id: int, stakeholder_id: int, request: Request, db: Session = Depends(get_db)):
    project_service.remove_stakeholder(db, id, stakeholder_id)
    flash(request, "Стейкхолдер убран из проекта", "success")
    return RedirectResponse(_target(request, "project_detail", id=id) + "?tab=stk", status_code=302)


@router.post("/projects/{id}/add_employee", name="project_add_employee", dependencies=[Depends(require_admin)])
async def project_add_employee(id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    employee_id = _as_int(form.get("employee_id"))
    if project_service.add_employee(db, id, employee_id):
        flash(request, "Исполнитель добавлен к проекту", "success")
    else:
        flash(request, "Исполнитель уже в проекте", "warning")
    return RedirectResponse(_target(request, "project_detail", id=id) + "?tab=emp", status_code=302)


@router.get(
    "/projects/{id}/remove_employee/{employee_id}",
    name="project_remove_employee",
    dependencies=[Depends(require_admin)],
)
def project_remove_employee(id: int, employee_id: int, request: Request, db: Session = Depends(get_db)):
    project_service.remove_employee(db, id, employee_id)
    flash(request, "Исполнитель убран из проекта", "success")
    return RedirectResponse(_target(request, "project_detail", id=id) + "?tab=emp", status_code=302)


@router.get("/projects/{id}", name="project_detail")
def project_detail(id: int, request: Request, db: Session = Depends(get_db)):
    project = project_service.get_detail(db, id)
    if project is None:
        flash(request, "Проект не найден", "error")
        return RedirectResponse(_target(request, "projects_list"), status_code=302)

    requirements = requirement_service.for_project(db, id)
    tree = stage_service.project_tree(db, id)
    stakeholders = project_service.stakeholder_data(db, id)
    employees = project_service.employee_data(db, id)

    req_html, req_count = project_views.requirements_block(request, requirements, id)
    stages_html, stages_count = project_views.stage_tree_block(request, tree, id)
    stk_html, stk_count = project_views.stakeholders_block(request, stakeholders, id)
    emp_html, emp_count = project_views.employees_block(request, employees, id)

    active_tab = request.query_params.get("tab") or "req"
    if active_tab not in ("req", "stages", "stk", "emp"):
        active_tab = "req"
    request.session["project_id"] = id
    content = project_views.detail_content(
        request,
        project,
        req_html,
        req_count,
        stages_html,
        stages_count,
        stk_html,
        stk_count,
        emp_html,
        emp_count,
        active_tab,
    )
    return render(request, "pages/content.html", db, title=str(project["name"]), content=content)
