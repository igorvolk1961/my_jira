"""Этапы проектов: HTTP-контроллеры."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.flash import flash
from app.presentation import stage_views
from app.presentation.render import render
from app.services import stage_service

router = APIRouter()


def _target(request: Request, name: str, **params: object) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return str(request.url_for("index"))


@router.get("/project_stages", name="project_stages_list")
def project_stages_list(request: Request, db: Session = Depends(get_db)):
    stages = stage_service.list_stages(db)
    return render(
        request,
        "pages/list.html",
        db,
        title="Этапы проектов",
        table=stage_views.stages_table(request, stages),
        add_url=_target(request, "project_stage_create"),
        add_label="+ Добавить этап",
    )


@router.api_route(
    "/project_stages/create",
    methods=["GET", "POST"],
    name="project_stage_create",
    dependencies=[Depends(require_admin)],
)
async def project_stage_create(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error = stage_service.create(db, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Этап проекта создан", "success")
            return RedirectResponse(_target(request, "project_stages_list"), status_code=302)
    options = stage_service.form_options(db)
    return render(
        request,
        "pages/form.html",
        db,
        title="Новый этап проекта",
        action=_target(request, "project_stage_create"),
        fields=stage_views.stage_form_fields(options),
        submit_label="Создать",
        back_url=_target(request, "project_stages_list"),
    )


@router.api_route(
    "/project_stages/edit/{id}",
    methods=["GET", "POST"],
    name="project_stage_edit",
    dependencies=[Depends(require_admin)],
)
async def project_stage_edit(id: int, request: Request, db: Session = Depends(get_db)):
    stage, _tasks = stage_service.detail(db, id)
    if stage is None:
        flash(request, "Этап не найден", "error")
        return RedirectResponse(_target(request, "project_stages_list"), status_code=302)
    if request.method == "POST":
        form = dict(await request.form())
        error = stage_service.update(db, id, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Этап проекта обновлён", "success")
            return RedirectResponse(_target(request, "project_stages_list"), status_code=302)
    options = stage_service.form_options(db)
    return render(
        request,
        "pages/form.html",
        db,
        title="Редактировать этап проекта",
        action=_target(request, "project_stage_edit", id=id),
        fields=stage_views.stage_form_fields(options, stage),
        back_url=_target(request, "project_stages_list"),
    )


@router.get("/project_stages/delete/{id}", name="project_stage_delete", dependencies=[Depends(require_admin)])
def project_stage_delete(id: int, request: Request, db: Session = Depends(get_db)):
    stage_service.delete(db, id)
    flash(request, "Этап проекта удалён", "success")
    return RedirectResponse(_target(request, "project_stages_list"), status_code=302)


@router.get("/project_stages/{id}", name="project_stage_detail")
def project_stage_detail(id: int, request: Request, db: Session = Depends(get_db)):
    stage, tasks = stage_service.detail(db, id)
    if stage is None:
        flash(request, "Этап не найден", "error")
        return RedirectResponse(_target(request, "project_stages_list"), status_code=302)
    info, tables = stage_views.stage_detail(request, stage, tasks)
    return render(
        request,
        "pages/stage_detail.html",
        db,
        title="Этап: " + str(stage["type_name"]),
        info=info,
        tables=tables,
    )
