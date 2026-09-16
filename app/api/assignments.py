"""Назначения задач: HTTP-контроллеры."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin, require_user
from app.flash import flash
from app.presentation import assignment_views
from app.presentation.capabilities import is_admin
from app.presentation.render import render
from app.presentation.urls import safe_url
from app.security import safe_next
from app.services import assignment_service, settings_service, subtask_service, task_service
from app.services.support import to_int

router = APIRouter()


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=302)


def _back(request: Request, form: dict[str, Any]) -> str:
    origin = to_int(form.get("origin"))
    if origin:
        url = safe_url(request, "project_detail", id=origin)
        if url:
            return url
    fallback = str(request.url_for("task_assignments_list"))
    return safe_next(str(form.get("next") or ""), fallback)


@router.get("/task_assignments", name="task_assignments_list")
def task_assignments_list(request: Request, db: Session = Depends(get_db)):
    rows = assignment_service.list_assignments(db)
    return render(
        request,
        "pages/list.html",
        db,
        title="Назначения задач",
        table=assignment_views.assignment_table(request, rows),
        add_url=str(request.url_for("task_assignment_create")),
        add_label="+ Добавить назначение",
    )


@router.api_route(
    "/task_assignments/create",
    methods=["GET", "POST"],
    name="task_assignment_create",
    dependencies=[Depends(require_user)],
)
async def task_assignment_create(request: Request, db: Session = Depends(get_db), user: dict = Depends(require_user)):
    if request.method == "POST":
        form = dict(await request.form())
        error, message = assignment_service.create(db, form, user)
        if error:
            flash(request, error, "error")
        else:
            flash(request, message, "success")
        return _redirect(_back(request, form))

    if not is_admin(user):
        managed = subtask_service.managed_ids(db, user.get("employee_id"))
        subtasks = [s for s in subtask_service.list_active(db) if s["id"] in managed]
        if not subtasks:
            flash(request, "Нет подзадач, доступных вам для назначения исполнителя", "error")
            return _redirect(str(request.url_for("index")))
        allow_any = settings_service.allow_users_assign_subtask_executors(db)
        if allow_any:
            employees = task_service.employee_options(db)
            selected_employee = None
        else:
            employees = [
                {
                    "id": user.get("employee_id"),
                    "last_name": str(user.get("full_name") or ""),
                    "first_name": "",
                }
            ]
            selected_employee = user.get("employee_id")
        return render(
            request,
            "pages/form.html",
            db,
            title="Назначить исполнителя подзадачи",
            action=str(request.url_for("task_assignment_create")),
            fields=assignment_views.assignment_form_fields(
                tasks=[],
                subtasks=subtasks,
                employees=employees,
                selected_task_id=request.query_params.get("task_id"),
                selected_kind="subtask",
                selected_employee_id=selected_employee,
                task_kind_fixed="subtask",
                employee_required=False,
                employee_empty_label="— не назначен —",
            ),
            back_url=str(request.url_for("index")),
            submit_label="Сохранить",
        )

    pre_task = request.query_params.get("task_id")
    pre_kind = request.query_params.get("task_kind", "task")
    return render(
        request,
        "pages/form.html",
        db,
        title="Новое назначение",
        action=str(request.url_for("task_assignment_create")),
        fields=assignment_views.assignment_form_fields(
            tasks=task_service.task_options(db),
            subtasks=subtask_service.list_active(db),
            employees=task_service.employee_options(db),
            selected_task_id=pre_task,
            selected_kind=pre_kind,
            origin=request.query_params.get("origin"),
        ),
        back_url=str(request.url_for("task_assignments_list")),
        submit_label="Создать",
    )


@router.api_route(
    "/task_assignments/edit/{id}",
    methods=["GET", "POST"],
    name="task_assignment_edit",
    dependencies=[Depends(require_admin)],
)
async def task_assignment_edit(
    id: int, request: Request, db: Session = Depends(get_db), user: dict = Depends(require_admin)
):
    if request.method == "POST":
        form = dict(await request.form())
        error = assignment_service.update(db, id, form, user)
        if error:
            flash(request, error, "error")
            return _redirect(str(request.url_for("task_assignments_list")))
        flash(request, "Назначение обновлено", "success")
        return _redirect(str(request.url_for("task_assignments_list")))

    row = assignment_service.get_row(db, id)
    if row is None:
        flash(request, "Назначение не найдено", "error")
        return _redirect(str(request.url_for("task_assignments_list")))
    return render(
        request,
        "pages/form.html",
        db,
        title="Редактировать назначение",
        action=str(request.url_for("task_assignment_edit", id=id)),
        fields=assignment_views.assignment_form_fields(
            tasks=task_service.task_options(db),
            subtasks=subtask_service.list_active(db),
            employees=task_service.employee_options(db),
            selected_task_id=row["task_id"],
            selected_kind=row["task_kind"],
            selected_employee_id=row["employee_id"],
            share=row["share"],
        ),
        back_url=str(request.url_for("task_assignments_list")),
    )


@router.get(
    "/task_assignments/delete/{id}",
    name="task_assignment_delete",
    dependencies=[Depends(require_admin)],
)
def task_assignment_delete(id: int, request: Request, db: Session = Depends(get_db)):
    assignment_service.delete(db, id)
    flash(request, "Назначение удалено", "success")
    return _redirect(str(request.url_for("task_assignments_list")))


@router.get("/task_assignments/{id}", name="task_assignment_detail")
def task_assignment_detail(id: int, request: Request, db: Session = Depends(get_db)):
    row = assignment_service.get_row(db, id)
    if row is None:
        flash(request, "Назначение не найдено", "error")
        return _redirect(str(request.url_for("task_assignments_list")))
    return render(request, "pages/task_detail.html", db, **assignment_views.assignment_detail_context(request, row))
