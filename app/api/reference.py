"""Справочники: контроллеры CRUD (по конфигурации ресурсов)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import current_user, get_db, require_admin
from app.flash import flash
from app.presentation import views
from app.presentation.capabilities import is_admin
from app.presentation.render import render
from app.services import reference_service
from app.services.reference_service import RESOURCES, Resource

router = APIRouter()


def _list_view(resource: Resource):
    def view(request: Request, db: Session = Depends(get_db)):
        items = reference_service.list_items(db, resource)
        admin = is_admin(current_user(request, db))
        return render(
            request,
            "pages/list.html",
            db,
            title=resource.title,
            table=views.reference_table(request, resource, items, can_edit=admin),
            add_url=str(request.url_for(resource.create_name)) if admin else None,
            add_label="+ Добавить",
        )

    return view


def _create_view(resource: Resource):
    async def view(request: Request, db: Session = Depends(get_db)):
        if request.method == "POST":
            form = dict(await request.form())
            error = reference_service.create_item(db, resource, form)
            if error:
                flash(request, error, "error")
            else:
                flash(request, f"{resource.title}: запись создана", "success")
                return RedirectResponse(str(request.url_for(resource.list_name)), status_code=302)
        return render(
            request,
            "pages/form.html",
            db,
            title=f"{resource.title}: создание",
            action=str(request.url_for(resource.create_name)),
            fields=views.reference_form_fields(resource),
            back_url=str(request.url_for(resource.list_name)),
        )

    return view


def _edit_view(resource: Resource):
    async def view(id: int, request: Request, db: Session = Depends(get_db)):
        item = reference_service.get_item(db, resource, id)
        if item is None:
            flash(request, "Запись не найдена", "error")
            return RedirectResponse(str(request.url_for(resource.list_name)), status_code=302)
        if request.method == "POST":
            form = dict(await request.form())
            error = reference_service.update_item(db, resource, item, form)
            if error:
                flash(request, error, "error")
            else:
                flash(request, f"{resource.title}: запись обновлена", "success")
                return RedirectResponse(str(request.url_for(resource.list_name)), status_code=302)
        return render(
            request,
            "pages/form.html",
            db,
            title=f"{resource.title}: изменение",
            action=str(request.url_for(resource.edit_name, id=id)),
            fields=views.reference_form_fields(resource, item),
            back_url=str(request.url_for(resource.list_name)),
        )

    return view


def _delete_view(resource: Resource):
    def view(id: int, request: Request, db: Session = Depends(get_db)):
        item = reference_service.get_item(db, resource, id)
        if item is None:
            flash(request, "Запись не найдена", "error")
        else:
            reference_service.delete_item(db, item)
            flash(request, f"{resource.title}: запись удалена", "success")
        return RedirectResponse(str(request.url_for(resource.list_name)), status_code=302)

    return view


for _resource in RESOURCES.values():
    router.get(_resource.base_path, name=_resource.list_name)(_list_view(_resource))
    router.api_route(
        f"{_resource.base_path}/create",
        methods=["GET", "POST"],
        name=_resource.create_name,
        dependencies=[Depends(require_admin)],
    )(_create_view(_resource))
    router.api_route(
        f"{_resource.base_path}/edit/{{id}}",
        methods=["GET", "POST"],
        name=_resource.edit_name,
        dependencies=[Depends(require_admin)],
    )(_edit_view(_resource))
    router.get(
        f"{_resource.base_path}/delete/{{id}}",
        name=_resource.delete_name,
        dependencies=[Depends(require_admin)],
    )(_delete_view(_resource))
