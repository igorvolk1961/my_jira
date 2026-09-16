"""Управление базой данных: HTTP-контроллеры."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import current_db_name, current_user, get_db, require_admin
from app.flash import flash
from app.presentation import database_views
from app.presentation.capabilities import is_admin
from app.presentation.render import render
from app.services import database_service

router = APIRouter()


def _url(request: Request, endpoint: str, fallback: str, **params: Any) -> str:
    try:
        return str(request.url_for(endpoint, **params))
    except Exception:
        return fallback


def _form_text(form: Any, key: str) -> str | None:
    value = form.get(key)
    return value if isinstance(value, str) else None


def _redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(_url(request, "database_index", "/database"), status_code=302)


@router.get("/database", name="database_index")
def database_index(request: Request, db: Session = Depends(get_db)):
    current = current_db_name(request)
    files = database_service.databases()
    admin = is_admin(current_user(request, db))
    preselect = request.query_params.get("copy") or current
    return render(
        request,
        "pages/database_index.html",
        db,
        title="База данных",
        content=database_views.content(request, current=current, files=files, admin=admin, preselect=preselect),
    )


@router.post("/database/create", name="database_create", dependencies=[Depends(require_admin)])
async def database_create(request: Request):
    form = await request.form()
    result = database_service.create(_form_text(form, "name"))
    for category, message in result.flashes:
        flash(request, message, category)
    if result.switch_db:
        request.session["db_name"] = result.switch_db
    return _redirect(request)


@router.post("/database/copy", name="database_copy", dependencies=[Depends(require_admin)])
async def database_copy(request: Request):
    form = await request.form()
    result = database_service.copy(
        source=_form_text(form, "source"),
        name=_form_text(form, "name"),
        switch=bool(form.get("switch")),
        current_db=current_db_name(request),
    )
    for category, message in result.flashes:
        flash(request, message, category)
    if result.switch_db:
        request.session["db_name"] = result.switch_db
    return _redirect(request)


@router.get("/database/use/{name}", name="database_use", dependencies=[Depends(require_admin)])
def database_use(name: str, request: Request):
    result = database_service.use(name)
    for category, message in result.flashes:
        flash(request, message, category)
    if result.switch_db:
        request.session["db_name"] = result.switch_db
    return _redirect(request)


@router.get("/database/delete/{name}", name="database_delete", dependencies=[Depends(require_admin)])
def database_delete(name: str, request: Request):
    result = database_service.delete(name, current_db=current_db_name(request))
    for category, message in result.flashes:
        flash(request, message, category)
    if result.switch_db:
        request.session["db_name"] = result.switch_db
    return _redirect(request)
