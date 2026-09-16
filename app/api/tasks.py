"""Задачи и подзадачи: HTTP-контроллеры."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import current_user, get_db, require_admin, require_user
from app.flash import flash
from app.presentation import task_views
from app.presentation.capabilities import is_admin
from app.presentation.render import render
from app.presentation.urls import safe_url
from app.security import safe_next
from app.services import subtask_service, task_service
from app.services.support import to_int

router = APIRouter()


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=302)


def _origin_detail(request: Request, form: dict[str, Any], fallback: str) -> str:
    origin = to_int(form.get("origin"))
    if origin:
        url = safe_url(request, "project_detail", id=origin)
        if url:
            return url
    return str(request.url_for(fallback))


# ==================== ЗАДАЧИ ====================


@router.get("/tasks", name="tasks_list")
def tasks_list(request: Request, db: Session = Depends(get_db)):
    rows = task_service.list_tasks(db)
    admin = is_admin(current_user(request, db))
    return render(
        request,
        "pages/list.html",
        db,
        title="Задачи",
        table=task_views.task_table(request, rows, can_write=admin),
        add_url=str(request.url_for("task_create")) if admin else None,
        add_label="+ Добавить задачу",
    )


@router.api_route("/tasks/create", methods=["GET", "POST"], name="task_create", dependencies=[Depends(require_admin)])
async def task_create(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error, _task_id = task_service.create(db, form)
        if error:
            flash(request, error, "error")
            return _redirect(_origin_detail(request, form, "tasks_list"))
        flash(request, "Задача создана", "success")
        origin_id = to_int(form.get("origin"))
        if origin_id:
            stage_id = to_int(form.get("stage_id"))
            url = safe_url(request, "project_stage_detail", id=stage_id) if stage_id else None
            if url:
                return _redirect(url)
        return _redirect(str(request.url_for("tasks_list")))

    requirements = task_service.requirement_options(db)
    stages = task_service.stage_options(db)
    priorities = task_service.priority_options(db)
    statuses = task_service.status_list(db)
    task_types = task_service.task_type_options(db)

    origin = request.query_params.get("origin")
    preset_stage = request.query_params.get("stage_id")
    if not preset_stage and stages:
        chosen = stages[0]
        if origin is not None:
            for stage in stages:
                if str(stage["project_id"]) == str(origin):
                    chosen = stage
                    break
        preset_stage = str(chosen["id"])
    back_url = (safe_url(request, "project_detail", id=to_int(origin)) if origin else None) or str(
        request.url_for("tasks_list")
    )
    return render(
        request,
        "pages/form.html",
        db,
        title="Новая задача",
        action=str(request.url_for("task_create")),
        fields=task_views.task_form_fields(
            request,
            requirements=requirements,
            stages=stages,
            priorities=priorities,
            statuses=statuses,
            task_types=task_types,
            preset_stage_id=preset_stage,
            preset_requirement_id=request.query_params.get("requirement_id"),
            origin=origin,
        ),
        back_url=back_url,
        submit_label="Создать",
    )


@router.api_route("/tasks/edit/{id}", methods=["GET", "POST"], name="task_edit", dependencies=[Depends(require_admin)])
async def task_edit(id: int, request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error = task_service.update(db, id, form)
        if error:
            flash(request, error, "error")
            return _redirect(str(request.url_for("tasks_list")))
        flash(request, "Задача обновлена", "success")
        origin_id = to_int(form.get("origin"))
        if origin_id:
            url = safe_url(request, "project_detail", id=origin_id)
            if url:
                return _redirect(url)
        return _redirect(str(request.url_for("tasks_list")))

    task = task_service.get_row(db, id)
    if task is None:
        flash(request, "Задача не найдена", "error")
        return _redirect(str(request.url_for("tasks_list")))
    origin = request.query_params.get("origin")
    back_url = (safe_url(request, "project_detail", id=to_int(origin)) if origin else None) or str(
        request.url_for("tasks_list")
    )
    return render(
        request,
        "pages/form.html",
        db,
        title="Редактировать задачу",
        action=str(request.url_for("task_edit", id=id)),
        fields=task_views.task_form_fields(
            request,
            requirements=task_service.requirement_options(db),
            stages=task_service.stage_options(db),
            priorities=task_service.priority_options(db),
            statuses=task_service.status_list(db),
            task_types=task_service.task_type_options(db),
            task=task,
            origin=origin,
        ),
        back_url=back_url,
    )


@router.get("/tasks/delete/{id}", name="task_delete", dependencies=[Depends(require_admin)])
def task_delete(id: int, request: Request, db: Session = Depends(get_db)):
    task_service.delete(db, id)
    flash(request, "Задача удалена", "success")
    return _redirect(str(request.url_for("tasks_list")))


@router.post("/tasks/{id}/status", name="task_status_change", dependencies=[Depends(require_user)])
async def task_status_change(
    id: int, request: Request, db: Session = Depends(get_db), user: dict = Depends(require_user)
):
    form = await request.form()
    allowed, changed = task_service.change_status(db, id, to_int(form.get("status_id")), user)
    detail_url = str(request.url_for("task_detail", id=id))
    if not allowed:
        flash(request, "Недостаточно прав: задача назначена не на вас", "error")
        return _redirect(detail_url)
    if changed:
        flash(request, "Статус обновлён", "success")
    return _redirect(safe_next(str(form.get("next") or ""), detail_url))


# ==================== ПОДЗАДАЧИ ====================


@router.get("/subtasks", name="subtasks_list")
def subtasks_list(request: Request, db: Session = Depends(get_db)):
    rows = subtask_service.list_subtasks(db)
    return render(
        request,
        "pages/list.html",
        db,
        title="Подзадачи",
        table=task_views.subtask_table(request, rows),
        add_url=str(request.url_for("subtask_create")),
        add_label="+ Добавить подзадачу",
    )


@router.api_route(
    "/subtasks/create", methods=["GET", "POST"], name="subtask_create", dependencies=[Depends(require_user)]
)
async def subtask_create(request: Request, db: Session = Depends(get_db), user: dict = Depends(require_user)):
    if request.method == "POST":
        form = dict(await request.form())
        error, _subtask_id = subtask_service.create(db, form, user)
        if error:
            flash(request, error, "error")
            return _redirect(str(request.url_for("subtasks_list")))
        flash(request, "Подзадача создана", "success")
        origin_id = to_int(form.get("origin"))
        if origin_id:
            url = safe_url(request, "project_detail", id=origin_id)
            if url:
                return _redirect(url)
        return _redirect(str(request.url_for("subtasks_list")))

    pre_task = request.query_params.get("parent_task_id")
    pre_subtask = request.query_params.get("parent_subtask_id")
    origin = request.query_params.get("origin")
    root_task = pre_task
    preset_stage = None
    if pre_subtask:
        row = subtask_service.get_row(db, to_int(pre_subtask) or 0)
        if row:
            root_task = str(row["parent_task_id"])
            preset_stage = row["stage_id"]
    elif pre_task:
        row = task_service.get_row(db, to_int(pre_task) or 0)
        if row:
            preset_stage = row["stage_id"]
    back_url = (safe_url(request, "project_detail", id=to_int(origin)) if origin else None) or str(
        request.url_for("subtasks_list")
    )
    return render(
        request,
        "pages/form.html",
        db,
        title="Новая подзадача",
        action=str(request.url_for("subtask_create")),
        fields=task_views.subtask_form_fields(
            request,
            tasks=task_service.task_options(db),
            subtasks=subtask_service.list_active(db),
            stages=task_service.stage_options(db),
            priorities=task_service.priority_options(db),
            statuses=task_service.status_list(db),
            preset_task_id=root_task,
            preset_subtask_id=pre_subtask,
            preset_stage_id=preset_stage,
            origin=origin,
        ),
        back_url=back_url,
        submit_label="Создать",
    )


@router.api_route(
    "/subtasks/edit/{id}", methods=["GET", "POST"], name="subtask_edit", dependencies=[Depends(require_user)]
)
async def subtask_edit(id: int, request: Request, db: Session = Depends(get_db), user: dict = Depends(require_user)):
    employee_id = user.get("employee_id")
    if not is_admin(user) and not subtask_service.can_manage(db, employee_id, id):
        flash(request, "Недостаточно прав для изменения этой подзадачи", "error")
        return _redirect(str(request.url_for("subtasks_list")))
    if request.method == "POST":
        form = dict(await request.form())
        error = subtask_service.update(db, id, form, user)
        if error:
            flash(request, error, "error")
            return _redirect(str(request.url_for("subtasks_list")))
        flash(request, "Подзадача обновлена", "success")
        return _redirect(str(request.url_for("subtasks_list")))

    subtask = subtask_service.get_row(db, id)
    if subtask is None:
        flash(request, "Подзадача не найдена", "error")
        return _redirect(str(request.url_for("subtasks_list")))
    return render(
        request,
        "pages/form.html",
        db,
        title="Редактировать подзадачу",
        action=str(request.url_for("subtask_edit", id=id)),
        fields=task_views.subtask_form_fields(
            request,
            tasks=task_service.task_options(db),
            subtasks=subtask_service.list_active(db),
            stages=task_service.stage_options(db),
            priorities=task_service.priority_options(db),
            statuses=task_service.status_list(db),
            subtask=subtask,
        ),
        back_url=str(request.url_for("subtasks_list")),
    )


@router.get("/subtasks/delete/{id}", name="subtask_delete", dependencies=[Depends(require_user)])
def subtask_delete(id: int, request: Request, db: Session = Depends(get_db), user: dict = Depends(require_user)):
    error = subtask_service.delete(db, id, user)
    if error:
        flash(request, error, "error")
    else:
        flash(request, "Подзадача удалена", "success")
    return _redirect(str(request.url_for("subtasks_list")))


@router.post("/subtasks/{id}/status", name="subtask_status_change", dependencies=[Depends(require_user)])
async def subtask_status_change(
    id: int, request: Request, db: Session = Depends(get_db), user: dict = Depends(require_user)
):
    form = await request.form()
    allowed, changed = subtask_service.change_status(db, id, to_int(form.get("status_id")), user)
    detail_url = str(request.url_for("subtask_detail", id=id))
    if not allowed:
        flash(request, "Недостаточно прав: подзадача назначена не на вас", "error")
        return _redirect(detail_url)
    if changed:
        flash(request, "Статус обновлён", "success")
    return _redirect(safe_next(str(form.get("next") or ""), detail_url))


# ==================== ДЕТАЛЬНЫЕ СТРАНИЦЫ (после статических путей) ====================


@router.get("/tasks/{id}", name="task_detail")
def task_detail(id: int, request: Request, db: Session = Depends(get_db)):
    data = task_service.detail(db, id, current_user(request, db))
    if data is None:
        flash(request, "Задача не найдена", "error")
        return _redirect(str(request.url_for("tasks_list")))
    return render(request, "pages/task_detail.html", db, **task_views.task_detail_context(request, data))


@router.get("/subtasks/{id}", name="subtask_detail")
def subtask_detail(id: int, request: Request, db: Session = Depends(get_db)):
    data = subtask_service.detail(db, id, current_user(request, db))
    if data is None:
        flash(request, "Подзадача не найдена", "error")
        return _redirect(str(request.url_for("subtasks_list")))
    return render(request, "pages/task_detail.html", db, **task_views.subtask_detail_context(request, data))
