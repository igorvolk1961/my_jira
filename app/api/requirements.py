"""Требования: HTTP-контроллеры."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_analyst_or_admin
from app.flash import flash
from app.presentation import requirement_views
from app.presentation.render import render
from app.security import safe_next
from app.services import requirement_service

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


@router.get("/requirements", name="requirements_list")
def requirements_list(request: Request, db: Session = Depends(get_db)):
    requirements = requirement_service.list_requirements(db)
    return render(
        request,
        "pages/list.html",
        db,
        title="Требования",
        table=requirement_views.requirements_table(request, requirements),
        add_url=_target(request, "requirement_create"),
        add_label="+ Добавить требование",
    )


@router.api_route(
    "/requirements/create",
    methods=["GET", "POST"],
    name="requirement_create",
    dependencies=[Depends(require_analyst_or_admin)],
)
async def requirement_create(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        _new_id, error = requirement_service.create(db, form)
        if error:
            flash(request, error, "error")
            return RedirectResponse(_target(request, "requirement_create"), status_code=302)
        flash(request, "Требование создано", "success")
        next_url = str(form.get("next") or "")
        if next_url:
            return RedirectResponse(safe_next(next_url, _target(request, "requirements_list")), status_code=302)
        task_id = _as_int(form.get("task_id"))
        if task_id:
            return RedirectResponse(_target(request, "task_detail", id=task_id), status_code=302)
        return RedirectResponse(_target(request, "project_detail", id=_as_int(form.get("project_id"))), status_code=302)

    pre_project = request.query_params.get("project_id")
    pre_task = request.query_params.get("task_id")
    pre_type = request.query_params.get("requirement_type_id")
    pre_nfr = request.query_params.get("nfr_type_id")
    next_param: str | None = request.query_params.get("next")
    options = requirement_service.form_options(db)
    back_url = next_param or (
        _target(request, "task_detail", id=_as_int(pre_task))
        if pre_task
        else (
            _target(request, "project_detail", id=_as_int(pre_project))
            if pre_project
            else _target(request, "requirements_list")
        )
    )
    return render(
        request,
        "pages/form.html",
        db,
        title="Новое требование",
        action=_target(request, "requirement_create"),
        fields=requirement_views.requirement_form_fields(
            options,
            prefill={
                "project_id": _as_int(pre_project),
                "requirement_type_id": _as_int(pre_type),
                "nfr_type_id": _as_int(pre_nfr),
            },
            next_url=next_param,
            task_id=pre_task or "",
        ),
        submit_label="Создать",
        back_url=back_url,
    )


@router.api_route(
    "/requirements/edit/{id}",
    methods=["GET", "POST"],
    name="requirement_edit",
    dependencies=[Depends(require_analyst_or_admin)],
)
async def requirement_edit(id: int, request: Request, db: Session = Depends(get_db)):
    requirement, _tasks = requirement_service.detail(db, id)
    if requirement is None:
        flash(request, "Требование не найдено", "error")
        return RedirectResponse(_target(request, "requirements_list"), status_code=302)
    if request.method == "POST":
        form = dict(await request.form())
        error = requirement_service.update(db, id, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Требование обновлено", "success")
            next_url = str(form.get("next") or "")
            if next_url:
                return RedirectResponse(safe_next(next_url, _target(request, "requirements_list")), status_code=302)
            return RedirectResponse(_target(request, "requirements_list"), status_code=302)
    next_param: str | None = request.query_params.get("next")
    options = requirement_service.form_options(db)
    return render(
        request,
        "pages/form.html",
        db,
        title="Редактировать требование",
        action=_target(request, "requirement_edit", id=id),
        fields=requirement_views.requirement_form_fields(options, requirement, next_url=next_param),
        back_url=next_param or _target(request, "requirements_list"),
    )


@router.get("/requirements/delete/{id}", name="requirement_delete", dependencies=[Depends(require_analyst_or_admin)])
def requirement_delete(id: int, request: Request, db: Session = Depends(get_db)):
    requirement_service.delete(db, id)
    flash(request, "Требование удалено", "success")
    target = safe_next(request.query_params.get("next"), _target(request, "requirements_list"))
    return RedirectResponse(target, status_code=302)


@router.get("/requirements/{id}", name="requirement_detail")
def requirement_detail(id: int, request: Request, db: Session = Depends(get_db)):
    requirement, tasks = requirement_service.detail(db, id)
    if requirement is None:
        flash(request, "Требование не найдено", "error")
        return RedirectResponse(_target(request, "requirements_list"), status_code=302)
    info, tables = requirement_views.requirement_detail(request, requirement, tasks)
    return render(request, "pages/requirement_detail.html", db, title=f"Требование #{id}", info=info, tables=tables)
