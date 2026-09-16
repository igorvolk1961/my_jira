"""Комментарии: HTTP-контроллеры."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_user
from app.flash import flash
from app.presentation import comment_views
from app.presentation.render import render
from app.services import comment_service

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


def _entity_target(request: Request, entity_type: str | None, entity_id: int | None) -> str:
    name = "task_detail" if entity_type == "task" else "subtask_detail"
    target = _try_url(request, name, id=entity_id) if entity_id else None
    if target:
        return target
    return _try_url(request, "tasks_list") or "/"


def _redirect_target(
    request: Request,
    entity_type: str | None,
    entity_id: int | None,
    origin: int | None,
) -> str:
    if origin:
        return _try_url(request, "project_detail", id=origin, tab="stages") or f"/projects/{origin}?tab=stages"
    return _entity_target(request, entity_type, entity_id)


@router.api_route(
    "/comments/create",
    methods=["GET", "POST"],
    name="comment_create",
    dependencies=[Depends(require_user)],
)
async def comment_create(
    request: Request,
    db: Session = Depends(get_db),
    user: dict[str, Any] = Depends(require_user),
):
    if request.method == "POST":
        form = dict(await request.form())
        error, info = comment_service.create_comment(db, user, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Комментарий добавлен", "success")
        return RedirectResponse(
            _redirect_target(
                request,
                info.get("entity_type"),
                info.get("entity_id"),
                _int(form.get("origin")),
            ),
            status_code=302,
        )

    entity_type = str(request.query_params.get("entity_type") or "task")
    entity_id = _int(request.query_params.get("entity_id"))
    origin = _int(request.query_params.get("origin"))
    label = comment_service.entity_label(db, entity_type, entity_id) if entity_id else None
    context = comment_views.form_context(entity_type, entity_id, label, str(user.get("full_name") or ""))
    return render(
        request,
        "pages/comment_form.html",
        db,
        title="Новый комментарий",
        action=_url(request, "comment_create"),
        origin=origin,
        cancel_url=_redirect_target(request, entity_type, entity_id, origin),
        **context,
    )


@router.get("/comments/delete/{id}", name="comment_delete", dependencies=[Depends(require_user)])
def comment_delete(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: dict[str, Any] = Depends(require_user),
):
    origin = _int(request.query_params.get("origin"))
    error, comment = comment_service.delete_comment(db, user, id)
    if comment is None:
        flash(request, error or "Комментарий не найден", "error")
        return RedirectResponse(_try_url(request, "tasks_list") or "/", status_code=302)
    if error:
        flash(request, error, "error")
        return RedirectResponse(
            _redirect_target(request, comment.get("entity_type"), _int(comment.get("entity_id")), origin),
            status_code=302,
        )
    return RedirectResponse(
        _redirect_target(request, comment.get("entity_type"), _int(comment.get("entity_id")), origin),
        status_code=302,
    )
