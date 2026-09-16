"""Стейкхолдеры: HTTP-контроллеры."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import current_user, get_db, require_admin
from app.flash import flash
from app.presentation import stakeholder_views
from app.presentation.render import render
from app.services import stakeholder_service

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
    return _url(request, "stakeholders_list")


def _form_context(
    db: Session,
    request: Request,
    stakeholder: dict[str, Any] | None,
    *,
    title: str,
    submit_label: str,
    action: str,
    project_id: int | None,
    origin: int | None,
) -> dict[str, Any]:
    options = stakeholder_service.form_options(db, stakeholder["id"] if stakeholder else None)
    type_prio = ",".join(f"{t['id']}:{int(t['influence_priority'])}" for t in options["types"])
    return {
        "title": title,
        "submit_label": submit_label,
        "action": action,
        "stakeholder": stakeholder,
        "types": options["types"],
        "priorities": options["priorities"],
        "employees": options["employees"],
        "dev_id": options["dev_id"],
        "type_prio": type_prio,
        "project_id": project_id,
        "origin": origin,
        "cancel_url": _back_url(request, project_id or origin, "stk"),
    }


@router.get("/stakeholders", name="stakeholders_list")
def stakeholders_list(request: Request, db: Session = Depends(get_db)):
    stakeholders = stakeholder_service.list_stakeholders(db)
    user = current_user(request, db)
    is_admin = bool(user and user.get("role") == "admin")
    return render(
        request,
        "pages/list.html",
        db,
        title="Стейкхолдеры",
        table=stakeholder_views.list_table(request, stakeholders, is_admin),
        add_url=_url(request, "stakeholder_create") if is_admin else None,
        add_label="+ Добавить стейкхолдера",
    )


@router.api_route(
    "/stakeholders/create",
    methods=["GET", "POST"],
    name="stakeholder_create",
    dependencies=[Depends(require_admin)],
)
async def stakeholder_create(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error, _stakeholder_id = stakeholder_service.create_stakeholder(db, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Стейкхолдер создан", "success")
            return RedirectResponse(_back_url(request, _int(form.get("project_id")), "stk"), status_code=302)
    project_id = _int(request.query_params.get("project_id"))
    return render(
        request,
        "pages/stakeholder_form.html",
        db,
        **_form_context(
            db,
            request,
            None,
            title="Новый стейкхолдер",
            submit_label="Создать",
            action=_url(request, "stakeholder_create"),
            project_id=project_id,
            origin=None,
        ),
    )


@router.api_route(
    "/stakeholders/edit/{id}",
    methods=["GET", "POST"],
    name="stakeholder_edit",
    dependencies=[Depends(require_admin)],
)
async def stakeholder_edit(id: int, request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error = stakeholder_service.update_stakeholder(db, id, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Стейкхолдер обновлён", "success")
            return RedirectResponse(_back_url(request, _int(form.get("origin")), "stk"), status_code=302)
    stakeholder = stakeholder_service.get_stakeholder(db, id)
    if stakeholder is None:
        flash(request, "Стейкхолдер не найден", "error")
        return RedirectResponse(_url(request, "stakeholders_list"), status_code=302)
    origin = _int(request.query_params.get("origin"))
    return render(
        request,
        "pages/stakeholder_form.html",
        db,
        **_form_context(
            db,
            request,
            stakeholder,
            title="Редактировать стейкхолдера",
            submit_label="Сохранить",
            action=_url(request, "stakeholder_edit", id=id),
            project_id=None,
            origin=origin,
        ),
    )


@router.get("/stakeholders/delete/{id}", name="stakeholder_delete", dependencies=[Depends(require_admin)])
def stakeholder_delete(id: int, request: Request, db: Session = Depends(get_db)):
    stakeholder_service.delete_stakeholder(db, id)
    flash(request, "Стейкхолдер удалён", "success")
    return RedirectResponse(_url(request, "stakeholders_list"), status_code=302)


@router.get("/stakeholders/{id}", name="stakeholder_detail")
def stakeholder_detail(id: int, request: Request, db: Session = Depends(get_db)):
    data = stakeholder_service.stakeholder_detail(db, id)
    if not data:
        flash(request, "Стейкхолдер не найден", "error")
        return RedirectResponse(_url(request, "stakeholders_list"), status_code=302)
    stakeholder = data["stakeholder"]
    title = f"Стейкхолдер: {stakeholder['last_name']} {stakeholder['first_name']}"
    return render(
        request,
        "pages/stakeholder_detail.html",
        db,
        title=title,
        info=stakeholder_views.detail_info(stakeholder),
        tables=[
            stakeholder_views.projects_table(request, data["projects"]),
            stakeholder_views.requirements_table(request, data["requirements"]),
            stakeholder_views.interviews_table(request, data["interviews"]),
        ],
    )
