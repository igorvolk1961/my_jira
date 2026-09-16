"""Сотрудники: HTTP-контроллеры."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import current_user, get_db, require_admin
from app.flash import flash
from app.presentation import employee_views
from app.presentation.render import render
from app.services import employee_service

router = APIRouter()


def _try_url(request: Request, name: str, **params: Any) -> str | None:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return None


def _url(request: Request, name: str, **params: Any) -> str:
    return _try_url(request, name, **params) or "#"


def _int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _project_url(request: Request, project_id: int, tab: str) -> str:
    return _try_url(request, "project_detail", id=project_id, tab=tab) or f"/projects/{project_id}?tab={tab}"


def _back_url(request: Request, project_id: int | None, tab: str) -> str:
    if project_id:
        return _project_url(request, project_id, tab)
    return _url(request, "employees_list")


@router.get("/employees", name="employees_list")
def employees_list(request: Request, db: Session = Depends(get_db)):
    employees = employee_service.list_employees(db)
    user = current_user(request, db)
    is_admin = bool(user and user.get("role") == "admin")
    self_employee_id = user.get("employee_id") if user else None
    return render(
        request,
        "pages/list.html",
        db,
        title="Сотрудники",
        table=employee_views.list_table(request, employees, is_admin, self_employee_id),
        add_url=_url(request, "employee_create") if is_admin else None,
        add_label="+ Добавить сотрудника",
    )


@router.api_route(
    "/employees/create",
    methods=["GET", "POST"],
    name="employee_create",
    dependencies=[Depends(require_admin)],
)
async def employee_create(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error, _employee_id = employee_service.create_employee(db, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Сотрудник создан", "success")
            return RedirectResponse(_back_url(request, _int(form.get("project_id")), "emp"), status_code=302)
    options = employee_service.form_options(db)
    project_id = _int(request.query_params.get("project_id"))
    return render(
        request,
        "pages/form.html",
        db,
        title="Новый сотрудник",
        action=_url(request, "employee_create"),
        fields=employee_views.form_fields(None, options["positions"], options["statuses"], project_id=project_id),
        back_url=_back_url(request, project_id, "emp"),
    )


@router.api_route(
    "/employees/edit/{id}",
    methods=["GET", "POST"],
    name="employee_edit",
    dependencies=[Depends(require_admin)],
)
async def employee_edit(id: int, request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error = employee_service.update_employee(db, id, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Сотрудник обновлён", "success")
            origin = _int(form.get("origin"))
            return RedirectResponse(_back_url(request, origin, "emp"), status_code=302)
    employee = employee_service.get_employee(db, id)
    if employee is None:
        flash(request, "Сотрудник не найден", "error")
        return RedirectResponse(_url(request, "employees_list"), status_code=302)
    options = employee_service.form_options(db)
    origin = _int(request.query_params.get("origin"))
    return render(
        request,
        "pages/form.html",
        db,
        title="Редактировать сотрудника",
        action=_url(request, "employee_edit", id=id),
        fields=employee_views.form_fields(employee, options["positions"], options["statuses"], origin=origin),
        back_url=_back_url(request, origin, "emp"),
    )


@router.get("/employees/delete/{id}", name="employee_delete", dependencies=[Depends(require_admin)])
def employee_delete(id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    error, message = employee_service.delete_employee(db, id, user)
    flash(request, error or message, "error" if error else "success")
    return RedirectResponse(_url(request, "employees_list"), status_code=302)


@router.post("/employees/role/{id}", name="employee_role_change", dependencies=[Depends(require_admin)])
async def employee_role_change(id: int, request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    user = current_user(request, db)
    error = employee_service.change_role(db, id, form, user)
    flash(request, error or "Роли пользователя обновлены", "error" if error else "success")
    return RedirectResponse(_url(request, "employees_list"), status_code=302)


@router.get("/employees/{id}", name="employee_detail")
def employee_detail(id: int, request: Request, db: Session = Depends(get_db)):
    data = employee_service.employee_detail(db, id)
    if not data:
        flash(request, "Сотрудник не найден", "error")
        return RedirectResponse(_url(request, "employees_list"), status_code=302)
    employee = data["employee"]
    title = f"Сотрудник: {employee['last_name']} {employee['first_name']}"
    return render(
        request,
        "pages/employee_detail.html",
        db,
        title=title,
        info=employee_views.detail_info(employee, data["load"]),
        tables=[
            employee_views.tasks_table(request, data["tasks"]),
            employee_views.subtasks_table(request, data["subtasks"]),
        ],
    )
