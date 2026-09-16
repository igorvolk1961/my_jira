"""События: HTTP-контроллеры."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import current_user, get_db, require_admin
from app.flash import flash
from app.presentation import event_views
from app.presentation.render import render
from app.services import event_service

router = APIRouter()


def _url(request: Request, name: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return "#"


@router.get("/events", name="events_list")
def events_list(request: Request, db: Session = Depends(get_db)):
    events = event_service.list_events(db)
    user = current_user(request, db)
    is_admin = bool(user and user.get("role") == "admin")
    return render(
        request,
        "pages/list.html",
        db,
        title="События",
        table=event_views.list_table(request, events, is_admin),
        add_url=_url(request, "event_create") if is_admin else None,
        add_label="+ Добавить событие",
    )


@router.api_route(
    "/events/create",
    methods=["GET", "POST"],
    name="event_create",
    dependencies=[Depends(require_admin)],
)
async def event_create(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error, _event_id = event_service.create_event(db, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Событие создано", "success")
            return RedirectResponse(_url(request, "events_list"), status_code=302)
    return render(
        request,
        "pages/form.html",
        db,
        title="Новое событие",
        action=_url(request, "event_create"),
        fields=event_views.form_fields(None),
        back_url=_url(request, "events_list"),
    )


@router.api_route(
    "/events/edit/{id}",
    methods=["GET", "POST"],
    name="event_edit",
    dependencies=[Depends(require_admin)],
)
async def event_edit(id: int, request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error = event_service.update_event(db, id, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Событие обновлено", "success")
            return RedirectResponse(_url(request, "events_list"), status_code=302)
    event = event_service.get_event(db, id)
    if event is None:
        flash(request, "Событие не найдено", "error")
        return RedirectResponse(_url(request, "events_list"), status_code=302)
    return render(
        request,
        "pages/form.html",
        db,
        title="Редактировать событие",
        action=_url(request, "event_edit", id=id),
        fields=event_views.form_fields(event),
        back_url=_url(request, "events_list"),
    )


@router.get("/events/delete/{id}", name="event_delete", dependencies=[Depends(require_admin)])
def event_delete(id: int, request: Request, db: Session = Depends(get_db)):
    event_service.delete_event(db, id)
    flash(request, "Событие удалено", "success")
    return RedirectResponse(_url(request, "events_list"), status_code=302)


@router.get("/events/{id}", name="event_detail")
def event_detail(id: int, request: Request, db: Session = Depends(get_db)):
    event = event_service.get_event(db, id)
    if event is None:
        flash(request, "Событие не найдено", "error")
        return RedirectResponse(_url(request, "events_list"), status_code=302)
    return render(
        request,
        "pages/event_detail.html",
        db,
        title=f"Событие #{id}",
        info=event_views.detail_info(event),
        tables=[],
    )
