"""Интервью: HTTP-контроллеры (интервью, вопросы-ответы, аудио, транскрипт, шаблоны)."""

import os
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.dependencies import current_user, get_db, require_admin
from app.flash import flash
from app.presentation import interview_views
from app.presentation.render import render
from app.services import interview_service
from app.services.support import to_int

router = APIRouter()


def _url(request: Request, name: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return "#"


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=302)


def _is_admin(request: Request, db: Session) -> bool:
    user = current_user(request, db)
    return bool(user and user.get("role") == "admin")


# ==================== ИНТЕРВЬЮ ====================


@router.get("/interviews", name="interviews_list")
def interviews_list(request: Request, db: Session = Depends(get_db)):
    items = interview_service.list_interviews(db)
    admin = _is_admin(request, db)
    templates_url = _url(request, "interview_templates_list")
    return render(
        request,
        "pages/list.html",
        db,
        title="Интервью",
        table=interview_views.list_table(request, items, admin),
        add_url=_url(request, "interview_create") if admin else None,
        add_label="+ Назначить интервью",
        post_html=f'<a href="{templates_url}" class="btn btn-primary">Шаблоны интервью</a>',
    )


@router.api_route(
    "/interviews/create",
    methods=["GET", "POST"],
    name="interview_create",
    dependencies=[Depends(require_admin)],
)
async def interview_create(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error, new_id, copied = interview_service.create_interview(db, form)
        if error:
            flash(request, error, "error")
        elif new_id:
            message = "Интервью назначено"
            if copied:
                message += f"; добавлено вопросов из шаблона: {copied}"
            flash(request, message, "success")
            return _redirect(_url(request, "interview_detail", id=new_id))
    return render(
        request,
        "pages/form.html",
        db,
        title="Новое интервью",
        action=_url(request, "interview_create"),
        fields=interview_views.interview_form_fields(
            interview_service.stakeholder_options(db),
            interview_service.template_options(db),
            prefill_stakeholder=request.query_params.get("stakeholder_id"),
            prefill_template=request.query_params.get("template_id"),
        ),
        back_url=_url(request, "interviews_list"),
    )


@router.api_route(
    "/interviews/edit/{id}",
    methods=["GET", "POST"],
    name="interview_edit",
    dependencies=[Depends(require_admin)],
)
async def interview_edit(id: int, request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error = interview_service.update_interview(db, id, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Интервью обновлено", "success")
            return _redirect(_url(request, "interview_detail", id=id))
    interview = interview_service.get_interview(db, id)
    if interview is None:
        flash(request, "Интервью не найдено", "error")
        return _redirect(_url(request, "interviews_list"))
    return render(
        request,
        "pages/form.html",
        db,
        title="Редактировать интервью",
        action=_url(request, "interview_edit", id=id),
        fields=interview_views.interview_form_fields(
            interview_service.stakeholder_options(db),
            interview_service.template_options(db),
            interview=interview,
        ),
        back_url=_url(request, "interview_detail", id=id),
    )


@router.get("/interviews/delete/{id}", name="interview_delete", dependencies=[Depends(require_admin)])
def interview_delete(id: int, request: Request, db: Session = Depends(get_db)):
    interview_service.delete_interview(db, id)
    flash(request, "Интервью удалено", "success")
    return _redirect(_url(request, "interviews_list"))


# ==================== АУДИО (литералы раньше динамических путей) ====================


@router.post(
    "/interviews/{id}/audio",
    name="interview_audio_upload",
    dependencies=[Depends(require_admin)],
)
async def interview_audio_upload(id: int, request: Request, db: Session = Depends(get_db)):
    detail_url = _url(request, "interview_detail", id=id)
    form = await request.form()
    upload = form.get("file")
    if not isinstance(upload, UploadFile) or not upload.filename:
        flash(request, "Файл не выбран", "error")
        return _redirect(detail_url)
    content = await upload.read()
    duration_ms = to_int(form.get("duration_ms"))
    interview_service.save_audio(
        db,
        id,
        content,
        upload.filename,
        upload.content_type,
        duration_ms,
    )
    flash(request, "Аудиозапись загружена", "success")
    return _redirect(detail_url)


@router.get("/interviews/audio/{aid}", name="interview_audio_get")
def interview_audio_get(aid: int, request: Request, db: Session = Depends(get_db)):
    audio = interview_service.get_audio(db, aid)
    if audio is None:
        flash(request, "Аудиозапись не найдена", "error")
        return _redirect(_url(request, "interviews_list"))
    path = interview_service.audio_path(audio)
    if not os.path.exists(path):
        flash(request, "Аудиозапись не найдена", "error")
        return _redirect(_url(request, "interviews_list"))
    return FileResponse(path, media_type=audio.get("mime") or "application/octet-stream")


@router.get("/interviews/audio/{aid}/download", name="interview_audio_download")
def interview_audio_download(aid: int, request: Request, db: Session = Depends(get_db)):
    audio = interview_service.get_audio(db, aid)
    if audio is None:
        flash(request, "Аудиозапись не найдена", "error")
        return _redirect(_url(request, "interviews_list"))
    path = interview_service.audio_path(audio)
    if not os.path.exists(path):
        flash(request, "Аудиозапись не найдена", "error")
        return _redirect(_url(request, "interviews_list"))
    return FileResponse(
        path,
        media_type=audio.get("mime") or "application/octet-stream",
        filename=str(audio.get("original_name") or audio.get("filename") or f"audio_{aid}"),
    )


@router.get(
    "/interviews/audio/{aid}/delete",
    name="interview_audio_delete",
    dependencies=[Depends(require_admin)],
)
def interview_audio_delete(aid: int, request: Request, db: Session = Depends(get_db)):
    interview_id = interview_service.delete_audio(db, aid)
    if interview_id is None:
        flash(request, "Аудиозапись не найдена", "error")
        return _redirect(_url(request, "interviews_list"))
    flash(request, "Аудиозапись удалена", "success")
    return _redirect(_url(request, "interview_detail", id=interview_id))


# ==================== ТРАНСКРИПТ ====================


@router.post(
    "/interviews/{id}/transcribe",
    name="interview_transcribe",
    dependencies=[Depends(require_admin)],
)
async def interview_transcribe(id: int, request: Request, db: Session = Depends(get_db)):
    detail_url = _url(request, "interview_detail", id=id)
    try:
        form = await request.form()
        audio = interview_service.select_transcription_audio(db, id, form.get("audio_id"))
        if audio is None:
            flash(request, "Сначала загрузите или запишите аудио", "error")
            return _redirect(detail_url)
        path = interview_service.audio_path(audio)
        if not os.path.exists(path):
            flash(request, "Аудиофайл не найден на диске", "error")
            return _redirect(detail_url)
        try:
            segments = await run_in_threadpool(interview_service.transcribe_audio, path)
        except Exception as exc:
            flash(request, f"Распознавание недоступно: {exc}", "error")
            return _redirect(detail_url)
        count = interview_service.replace_segments(db, id, int(audio["id"]), segments)
        flash(request, f"Распознано сегментов: {count}", "success")
        return _redirect(detail_url)
    except Exception as exc:
        flash(request, f"Распознавание недоступно: {exc}", "error")
        return _redirect(detail_url)


@router.get(
    "/interviews/{id}/transcript/edit",
    name="transcript_edit",
    dependencies=[Depends(require_admin)],
)
def transcript_edit(id: int, request: Request, db: Session = Depends(get_db)):
    interview = interview_service.get_interview(db, id)
    if interview is None:
        flash(request, "Интервью не найдено", "error")
        return _redirect(_url(request, "interviews_list"))
    segments = interview_service.list_segments(db, id)
    return render(
        request,
        "pages/interview_transcript_edit.html",
        db,
        title="Редактирование транскрипта",
        **interview_views.transcript_edit_context(request, id, segments),
    )


@router.post(
    "/interviews/{id}/transcript/save",
    name="transcript_segments_save",
    dependencies=[Depends(require_admin)],
)
async def transcript_segments_save(id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    fields: dict[str, Any] = {key: form.get(key) for key in form}
    saved = interview_service.save_transcript_form(db, id, fields)
    flash(request, f"Сохранено сегментов: {saved}", "success")
    return _redirect(_url(request, "interview_detail", id=id))


@router.post(
    "/interviews/{id}/segments/clear",
    name="transcript_clear",
    dependencies=[Depends(require_admin)],
)
def transcript_clear(id: int, request: Request, db: Session = Depends(get_db)):
    interview_service.clear_segments(db, id)
    flash(request, "Транскрипт очищен", "success")
    return _redirect(_url(request, "interview_detail", id=id))


@router.get(
    "/interviews/{id}/segment/{sid}/delete",
    name="transcript_segment_delete",
    dependencies=[Depends(require_admin)],
)
def transcript_segment_delete(id: int, sid: int, request: Request, db: Session = Depends(get_db)):
    interview_service.delete_segment(db, id, sid)
    flash(request, "Сегмент удалён", "success")
    return _redirect(_url(request, "interview_detail", id=id))


# ==================== ЭКСПОРТ И ДЕТАЛИ ====================


@router.get("/interviews/{id}/export", name="interview_export")
def interview_export(id: int, request: Request, db: Session = Depends(get_db)):
    result = interview_service.build_export_markdown(db, id)
    if result is None:
        flash(request, "Интервью не найдено", "error")
        return _redirect(_url(request, "interviews_list"))
    filename, markdown = result
    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/interviews/{id}", name="interview_detail")
def interview_detail(id: int, request: Request, db: Session = Depends(get_db)):
    interview = interview_service.get_interview(db, id)
    if interview is None:
        flash(request, "Интервью не найдено", "error")
        return _redirect(_url(request, "interviews_list"))
    qas = interview_service.list_qa(db, id)
    audios = interview_service.list_audio(db, id)
    segments = interview_service.list_segments(db, id)
    return render(
        request,
        "pages/interview_detail.html",
        db,
        title=f"Интервью #{id}",
        **interview_views.detail_context(request, interview, qas, audios, segments, _is_admin(request, db)),
    )


@router.api_route(
    "/interviews/{id}/save_as_template",
    methods=["GET", "POST"],
    name="interview_save_as_template",
    dependencies=[Depends(require_admin)],
)
async def interview_save_as_template(id: int, request: Request, db: Session = Depends(get_db)):
    interview = interview_service.get_interview(db, id)
    if interview is None:
        flash(request, "Интервью не найдено", "error")
        return _redirect(_url(request, "interviews_list"))
    if request.method == "POST":
        form = dict(await request.form())
        error, template_id = interview_service.save_interview_as_template(db, id, form)
        if error:
            flash(request, error, "error")
        elif template_id:
            flash(
                request,
                f"Создан шаблон из интервью #{id} (вопросов: {len(interview_service.list_qa(db, id))})",
                "success",
            )
            return _redirect(_url(request, "interview_template_detail", id=template_id))
    return render(
        request,
        "pages/form.html",
        db,
        title="Шаблон из интервью",
        action=_url(request, "interview_save_as_template", id=id),
        fields=interview_views.save_template_form_fields(id, f"Шаблон по интервью #{id}"),
        back_url=_url(request, "interview_detail", id=id),
        submit_label="Создать шаблон",
    )


# ==================== ВОПРОСЫ-ОТВЕТЫ ====================


@router.api_route(
    "/interview_qa/create",
    methods=["GET", "POST"],
    name="interview_qa_create",
    dependencies=[Depends(require_admin)],
)
async def interview_qa_create(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error, interview_id = interview_service.create_qa(db, form)
        if error:
            flash(request, error, "error")
        elif interview_id:
            flash(request, "Вопрос добавлен", "success")
            return _redirect(_url(request, "interview_detail", id=interview_id))
    pre_interview = request.query_params.get("interview_id")
    cancel_url = (
        _url(request, "interview_detail", id=int(pre_interview))
        if pre_interview and pre_interview.isdigit()
        else _url(request, "interviews_list")
    )
    return render(
        request,
        "pages/form.html",
        db,
        title="Новый вопрос-ответ",
        action=_url(request, "interview_qa_create"),
        fields=interview_views.qa_form_fields(interview_service.interview_options(db), prefill_interview=pre_interview),
        back_url=cancel_url,
    )


@router.api_route(
    "/interview_qa/edit/{id}",
    methods=["GET", "POST"],
    name="interview_qa_edit",
    dependencies=[Depends(require_admin)],
)
async def interview_qa_edit(id: int, request: Request, db: Session = Depends(get_db)):
    qa = interview_service.get_qa(db, id)
    if qa is None:
        flash(request, "Вопрос-ответ не найден", "error")
        return _redirect(_url(request, "interviews_list"))
    if request.method == "POST":
        form = dict(await request.form())
        error, interview_id = interview_service.update_qa(db, id, form)
        if error:
            flash(request, error, "error")
        elif interview_id:
            flash(request, "Вопрос-ответ обновлён", "success")
            return _redirect(_url(request, "interview_detail", id=interview_id))
    return render(
        request,
        "pages/form.html",
        db,
        title="Редактировать вопрос-ответ",
        action=_url(request, "interview_qa_edit", id=id),
        fields=interview_views.qa_form_fields(interview_service.interview_options(db), qa=qa),
        back_url=_url(request, "interview_detail", id=int(qa["interview_id"])),
    )


@router.get("/interview_qa/delete/{id}", name="interview_qa_delete", dependencies=[Depends(require_admin)])
def interview_qa_delete(id: int, request: Request, db: Session = Depends(get_db)):
    interview_id = interview_service.delete_qa(db, id)
    if interview_id is None:
        flash(request, "Вопрос-ответ не найден", "error")
        return _redirect(_url(request, "interviews_list"))
    flash(request, "Вопрос-ответ удалён", "success")
    return _redirect(_url(request, "interview_detail", id=interview_id))


# ==================== ШАБЛОНЫ ИНТЕРВЬЮ ====================


@router.get("/interview_templates", name="interview_templates_list")
def interview_templates_list(request: Request, db: Session = Depends(get_db)):
    templates = interview_service.list_templates(db)
    admin = _is_admin(request, db)
    add_url = _url(request, "interview_template_create") if admin else None
    return render(
        request,
        "pages/list.html",
        db,
        title="Шаблоны интервью",
        table=interview_views.template_list_table(request, templates, admin),
        add_url=add_url,
        add_label="+ Создать шаблон",
        post_html=f'<a href="{_url(request, "interviews_list")}" class="btn btn-primary">К интервью</a>',
    )


@router.api_route(
    "/interview_templates/create",
    methods=["GET", "POST"],
    name="interview_template_create",
    dependencies=[Depends(require_admin)],
)
async def interview_template_create(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = dict(await request.form())
        error, template_id = interview_service.create_template(db, form)
        if error:
            flash(request, error, "error")
        elif template_id:
            flash(request, "Шаблон создан", "success")
            return _redirect(_url(request, "interview_template_detail", id=template_id))
    return render(
        request,
        "pages/form.html",
        db,
        title="Новый шаблон интервью",
        action=_url(request, "interview_template_create"),
        fields=interview_views.template_form_fields(),
        back_url=_url(request, "interview_templates_list"),
    )


@router.get(
    "/interview_templates/delete/{id}",
    name="interview_template_delete",
    dependencies=[Depends(require_admin)],
)
def interview_template_delete(id: int, request: Request, db: Session = Depends(get_db)):
    interview_service.delete_template(db, id)
    flash(request, "Шаблон удалён", "success")
    return _redirect(_url(request, "interview_templates_list"))


@router.api_route(
    "/interview_templates/{id}/question/create",
    methods=["GET", "POST"],
    name="interview_template_question_create",
    dependencies=[Depends(require_admin)],
)
async def interview_template_question_create(id: int, request: Request, db: Session = Depends(get_db)):
    template = interview_service.get_template(db, id)
    if template is None:
        flash(request, "Шаблон не найден", "error")
        return _redirect(_url(request, "interview_templates_list"))
    if request.method == "POST":
        form = dict(await request.form())
        error = interview_service.create_template_question(db, id, form)
        if error:
            flash(request, error, "error")
        else:
            flash(request, "Вопрос добавлен", "success")
            return _redirect(_url(request, "interview_template_detail", id=id))
    return render(
        request,
        "pages/form.html",
        db,
        title="Новый вопрос шаблона",
        action=_url(request, "interview_template_question_create", id=id),
        fields=interview_views.template_question_form_fields(),
        back_url=_url(request, "interview_template_detail", id=id),
    )


@router.api_route(
    "/interview_templates/question/edit/{id}",
    methods=["GET", "POST"],
    name="interview_template_question_edit",
    dependencies=[Depends(require_admin)],
)
async def interview_template_question_edit(id: int, request: Request, db: Session = Depends(get_db)):
    question = interview_service.get_template_question(db, id)
    if question is None:
        flash(request, "Вопрос не найден", "error")
        return _redirect(_url(request, "interview_templates_list"))
    if request.method == "POST":
        form = dict(await request.form())
        error, template_id = interview_service.update_template_question(db, id, form)
        if error:
            flash(request, error, "error")
        elif template_id:
            flash(request, "Вопрос обновлён", "success")
            return _redirect(_url(request, "interview_template_detail", id=template_id))
    return render(
        request,
        "pages/form.html",
        db,
        title="Редактировать вопрос шаблона",
        action=_url(request, "interview_template_question_edit", id=id),
        fields=interview_views.template_question_form_fields(question),
        back_url=(
            _url(request, "interview_template_detail", id=int(question["template_id"]))
            if question.get("template_id")
            else _url(request, "interview_templates_list")
        ),
    )


@router.get(
    "/interview_templates/question/delete/{id}",
    name="interview_template_question_delete",
    dependencies=[Depends(require_admin)],
)
def interview_template_question_delete(id: int, request: Request, db: Session = Depends(get_db)):
    template_id = interview_service.delete_template_question(db, id)
    if template_id is None:
        flash(request, "Вопрос не найден", "error")
        return _redirect(_url(request, "interview_templates_list"))
    flash(request, "Вопрос удалён", "success")
    return _redirect(_url(request, "interview_template_detail", id=template_id))


@router.get("/interview_templates/{id}", name="interview_template_detail")
def interview_template_detail(id: int, request: Request, db: Session = Depends(get_db)):
    template = interview_service.get_template(db, id)
    if template is None:
        flash(request, "Шаблон не найден", "error")
        return _redirect(_url(request, "interview_templates_list"))
    questions = interview_service.list_template_questions(db, id)
    return render(
        request,
        "pages/detail.html",
        db,
        title=str(template["name"]),
        **interview_views.template_detail_context(request, template, questions, _is_admin(request, db)),
    )
