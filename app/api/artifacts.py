"""Артефакты СА и пользовательские истории: HTTP-контроллеры."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import current_project, current_user, get_db, require_analyst_or_admin
from app.flash import flash
from app.presentation import artifact_views
from app.presentation.capabilities import can_edit_artifacts
from app.presentation.render import render
from app.services import artifact_service, project_service

router = APIRouter()


def _target(request: Request, name: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return str(request.url_for("index"))


def _user_stories_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(_target(request, "artifact_view", key="user_stories"), status_code=302)


# ==================== ПОЛЬЗОВАТЕЛЬСКИЕ ИСТОРИИ (литеральные пути — раньше {key}) ====================


@router.post(
    "/artifacts/user_stories/create",
    name="user_story_create",
    dependencies=[Depends(require_analyst_or_admin)],
)
async def user_story_create(request: Request, db: Session = Depends(get_db)):
    project = current_project(request, db)
    if not project:
        flash(request, "Сначала выберите проект", "error")
        return _user_stories_redirect(request)
    form = dict(await request.form())
    artifact_service.create_story(db, int(project["id"]), form)
    flash(request, "История добавлена", "success")
    return _user_stories_redirect(request)


@router.post(
    "/artifacts/user_stories/edit/{id}",
    name="user_story_edit",
    dependencies=[Depends(require_analyst_or_admin)],
)
async def user_story_edit(id: int, request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    error = artifact_service.update_story(db, id, form)
    if error:
        flash(request, error, "error")
    else:
        flash(request, "История обновлена", "success")
    return _user_stories_redirect(request)


@router.get(
    "/artifacts/user_stories/delete/{id}",
    name="user_story_delete",
    dependencies=[Depends(require_analyst_or_admin)],
)
def user_story_delete(id: int, request: Request, db: Session = Depends(get_db)):
    artifact_service.delete_story(db, id)
    flash(request, "История удалена", "success")
    return _user_stories_redirect(request)


@router.post(
    "/artifacts/user_stories/sections/create",
    name="user_story_section_create",
    dependencies=[Depends(require_analyst_or_admin)],
)
async def user_story_section_create(request: Request, db: Session = Depends(get_db)):
    project = current_project(request, db)
    form = dict(await request.form())
    name = str(form.get("name") or "")
    if not project:
        flash(request, "Укажите проект и название раздела", "error")
        return _user_stories_redirect(request)
    error = artifact_service.create_section(db, int(project["id"]), name)
    if error:
        flash(request, error, "error")
    else:
        flash(request, "Раздел добавлен", "success")
    return _user_stories_redirect(request)


@router.post(
    "/artifacts/user_stories/sections/edit/{id}",
    name="user_story_section_edit",
    dependencies=[Depends(require_analyst_or_admin)],
)
async def user_story_section_edit(id: int, request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    error = artifact_service.rename_section(db, id, str(form.get("name") or ""))
    if error:
        flash(request, error, "error")
    else:
        flash(request, "Раздел переименован", "success")
    return _user_stories_redirect(request)


@router.get(
    "/artifacts/user_stories/sections/delete/{id}",
    name="user_story_section_delete",
    dependencies=[Depends(require_analyst_or_admin)],
)
def user_story_section_delete(id: int, request: Request, db: Session = Depends(get_db)):
    error = artifact_service.delete_section(db, id)
    if error:
        flash(request, error, "error")
    else:
        flash(request, "Раздел удалён", "success")
    return _user_stories_redirect(request)


@router.post(
    "/artifacts/user_stories/reorder",
    name="user_story_reorder",
    dependencies=[Depends(require_analyst_or_admin)],
)
async def user_story_reorder(request: Request, db: Session = Depends(get_db)):
    project = current_project(request, db)
    if not project:
        return JSONResponse({"ok": False, "error": "no project"}, status_code=400)
    try:
        data = await request.json()
    except ValueError:
        data = {}
    artifact_service.reorder(db, int(project["id"]), data or {})
    return JSONResponse({"ok": True})


# ==================== АРТЕФАКТЫ (общие пути {key}) ====================


@router.get("/artifacts/{key}", name="artifact_view")
def artifact_view(key: str, request: Request, db: Session = Depends(get_db)):
    artifact = artifact_service.ARTIFACTS_BY_KEY.get(key)
    if not artifact:
        flash(request, "Артефакт не найден", "error")
        return RedirectResponse(_target(request, "index"), status_code=302)

    project = current_project(request, db)
    if not project:
        return render(
            request,
            "pages/artifact_view.html",
            db,
            title=str(artifact["title"]),
            no_project=True,
        )

    data = artifact_service.body_data(db, artifact, int(project["id"]))
    user = current_user(request, db)
    can_edit = can_edit_artifacts(user)
    body = artifact_views.artifact_body(request, artifact, project, data, can_edit, user is not None)
    header_buttons = (
        artifact_views.user_stories_header_buttons(request, project) if artifact["kind"] == "user_stories" else ""
    )
    projects = project_service.list_projects(db)
    return render(
        request,
        "pages/artifact_view.html",
        db,
        title=str(artifact["title"]),
        artifact_title=str(artifact["title"]),
        project=project,
        body=body,
        header_buttons=header_buttons,
        projects=projects,
        head_html="",
    )


@router.api_route(
    "/artifacts/{key}/edit",
    methods=["GET", "POST"],
    name="artifact_edit",
    dependencies=[Depends(require_analyst_or_admin)],
)
async def artifact_edit(key: str, request: Request, db: Session = Depends(get_db)):
    artifact = artifact_service.ARTIFACTS_BY_KEY.get(key)
    if not artifact or artifact["kind"] not in artifact_service.EDITABLE_KINDS:
        flash(request, "Артефакт не найден или не поддерживает правку", "error")
        return RedirectResponse(_target(request, "artifact_view", key=key), status_code=302)

    project = current_project(request, db)
    if not project:
        return render(
            request,
            "pages/artifact_view.html",
            db,
            title=str(artifact["title"]),
            no_project=True,
        )

    if request.method == "POST":
        form = dict(await request.form())
        user = current_user(request, db)
        artifact_service.save_document(
            db,
            int(project["id"]),
            str(artifact["key"]),
            str(form.get("content") or ""),
            user["id"] if user else None,
        )
        flash(request, "Артефакт сохранён", "success")
        return RedirectResponse(_target(request, "artifact_view", key=key), status_code=302)

    is_bpmn = artifact["kind"] == "bpmn"
    current_text = artifact_service.content(db, int(project["id"]), key)
    return render(
        request,
        "pages/artifact_edit.html",
        db,
        title="Редактировать: " + str(artifact["title"]),
        artifact_title=str(artifact["title"]),
        project=project,
        is_bpmn=is_bpmn,
        current_text=current_text,
        back_url=_target(request, "artifact_view", key=key),
        head_html=artifact_views.bpmn_head_html(request) if is_bpmn else "",
        modeler_url=_target(request, "static", path="bpmn/bpmn-modeler.production.min.js"),
        initial_xml=current_text,
    )


@router.get(
    "/artifacts/{key}/clear",
    name="artifact_clear",
    dependencies=[Depends(require_analyst_or_admin)],
)
def artifact_clear(key: str, request: Request, db: Session = Depends(get_db)):
    artifact = artifact_service.ARTIFACTS_BY_KEY.get(key)
    if not artifact or artifact["kind"] not in artifact_service.EDITABLE_KINDS:
        flash(request, "Артефакт не найден или не поддерживает очистку", "error")
        return RedirectResponse(_target(request, "artifact_view", key=key), status_code=302)

    project = current_project(request, db)
    if project:
        artifact_service.clear_artifact(db, int(project["id"]), key)
    flash(request, "Артефакт очищен", "success")
    return RedirectResponse(_target(request, "artifact_view", key=key), status_code=302)
