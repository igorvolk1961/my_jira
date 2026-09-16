"""HTML-представление домена «Интервью» (без SQL и бизнес-логики)."""

import html
from typing import Any

from fastapi import Request

from app.services.interview_service import fmt_timecode

Row = dict[str, Any]

_RECORD_SCRIPT = """<script>
var mediaRecorder = null, chunks = [];
async function startRec() {
  try {
    var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    chunks = [];
    mediaRecorder.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
    mediaRecorder.onstop = async function () {
      var mt = mediaRecorder.mimeType || 'audio/webm';
      var ext = mt.indexOf('mp4') >= 0 ? 'm4a' : 'webm';
      var blob = new Blob(chunks, { type: mt });
      var fd = new FormData();
      fd.append('file', blob, 'record.' + ext);
      await fetch('__UPLOAD__', { method: 'POST', body: fd });
      location.reload();
    };
    mediaRecorder.start();
    document.getElementById('recStatus').textContent = '● запись…';
    document.getElementById('recStart').style.display = 'none';
    document.getElementById('recStop').style.display = 'inline-block';
  } catch (e) {
    document.getElementById('recStatus').textContent = 'Нет доступа к микрофону (нужен HTTPS или localhost)';
  }
}
function stopRec() {
  if (mediaRecorder) { mediaRecorder.stop(); document.getElementById('recStop').style.display = 'none';
    document.getElementById('recStatus').textContent = 'сохранение…'; }
}
function seek(ms) { var a = document.querySelector('audio.player'); if (a) { a.currentTime = ms / 1000; a.play(); } }
function busy(form, label) {
  var btn = form.querySelector('button[type="submit"]');
  if (btn) { btn.disabled = true; btn.textContent = label; }
  var st = document.getElementById('recStatus');
  if (st) { st.textContent = label + ' Подождите, повторно нажимать не нужно.'; }
  return true;
}
</script>"""


def _url(request: Request, name: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return "#"


def _anchor(request: Request, name: str, label: str, css: str, **params: Any) -> str:
    return f'<a href="{html.escape(_url(request, name, **params))}" class="{css}">{html.escape(label)}</a>'


def _link(request: Request, name: str, label: Any, **params: Any) -> str:
    url = _url(request, name, **params)
    if url == "#":
        return html.escape(str(label))
    return f'<a href="{html.escape(url)}">{html.escape(str(label))}</a>'


def _esc(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def _select_options(items: list[Row], label: Any, selected: Any = None, empty_label: str | None = None) -> list[Row]:
    options: list[Row] = []
    if empty_label is not None:
        options.append({"value": "", "label": empty_label, "selected": selected in (None, "", 0)})
    for item in items:
        options.append(
            {
                "value": item["id"],
                "label": label(item),
                "selected": selected is not None and str(item["id"]) == str(selected),
            }
        )
    return options


# ==================== СПИСОК ====================


def list_table(request: Request, interviews: list[Row], is_admin: bool) -> Row:
    rows: list[list[str]] = []
    for interview in interviews:
        actions = [_anchor(request, "interview_detail", "Открыть", "btn btn-success", id=interview["id"])]
        if is_admin:
            actions.append(_anchor(request, "interview_edit", "Изменить", "btn btn-primary", id=interview["id"]))
            actions.append(_anchor(request, "interview_delete", "Удалить", "btn btn-danger", id=interview["id"]))
        stakeholder = (
            f'<a href="{_esc(_url(request, "stakeholder_detail", id=interview["stakeholder_id"]))}">'
            f"{_esc(interview['last_name'])} {_esc(interview['first_name'])}</a>"
        )
        rows.append(
            [
                str(interview["id"]),
                stakeholder,
                _esc(interview.get("scheduled_at") or "-"),
                " ".join(actions),
            ]
        )
    return {
        "title": "Интервью стейкхолдеров",
        "headers": ["ID", "Стейкхолдер", "Дата-время", "Действия"],
        "rows": rows,
    }


# ==================== СПИСОК ШАБЛОНОВ ====================


def template_list_table(request: Request, templates: list[Row], is_admin: bool) -> Row:
    rows: list[list[str]] = []
    for template in templates:
        actions = [_anchor(request, "interview_template_detail", "Открыть", "btn btn-success", id=template["id"])]
        if is_admin:
            actions.append(
                _anchor(request, "interview_create", "Создать интервью", "btn btn-warning", template_id=template["id"])
            )
            actions.append(
                _anchor(request, "interview_template_delete", "Удалить", "btn btn-danger", id=template["id"])
            )
        rows.append(
            [
                str(template["id"]),
                _link(request, "interview_template_detail", template["name"], id=template["id"]),
                _esc(template.get("description") or "-"),
                str(template.get("q_count") or 0),
                " ".join(actions),
            ]
        )
    return {
        "title": "Шаблоны интервью",
        "headers": ["ID", "Название", "Описание", "Вопросов", "Действия"],
        "rows": rows,
    }


# ==================== ФОРМЫ ====================


def interview_form_fields(
    stakeholders: list[Row],
    templates: list[Row],
    interview: Row | None = None,
    prefill_stakeholder: Any = None,
    prefill_template: Any = None,
) -> list[Row]:
    current = interview or {}
    stakeholder_selected = current.get("stakeholder_id", prefill_stakeholder)
    template_selected = prefill_template
    fields: list[Row] = [
        {
            "name": "stakeholder_id",
            "label": "Стейкхолдер",
            "type": "select",
            "required": True,
            "options": _select_options(
                stakeholders, lambda s: f"{s['last_name']} {s['first_name']}", stakeholder_selected
            ),
        }
    ]
    if interview is None:
        fields.append(
            {
                "name": "template_id",
                "label": "Шаблон вопросов",
                "type": "select",
                "options": _select_options(
                    templates, lambda t: t["name"], template_selected, "— с нуля (без шаблона) —"
                ),
                "hint": "Можно создать с нуля или по шаблону интервью.",
            }
        )
    fields.append(
        {
            "name": "scheduled_at",
            "label": "Дата-время",
            "type": "datetime-local",
            "value": current.get("scheduled_at") or "",
        }
    )
    return fields


def qa_form_fields(interviews: list[Row], qa: Row | None = None, prefill_interview: Any = None) -> list[Row]:
    current = qa or {}
    interview_selected = current.get("interview_id", prefill_interview)
    return [
        {
            "name": "interview_id",
            "label": "Интервью",
            "type": "select",
            "required": True,
            "options": _select_options(interviews, lambda i: f"#{i['id']}", interview_selected),
        },
        {
            "name": "question",
            "label": "Вопрос",
            "type": "textarea",
            "required": True,
            "value": current.get("question") or "",
        },
        {
            "name": "answer",
            "label": "Ответ",
            "type": "textarea",
            "value": current.get("answer") or "",
        },
    ]


def template_form_fields(template: Row | None = None) -> list[Row]:
    current = template or {}
    return [
        {
            "name": "name",
            "label": "Название",
            "type": "text",
            "required": True,
            "value": current.get("name") or "",
        },
        {
            "name": "description",
            "label": "Описание",
            "type": "textarea",
            "value": current.get("description") or "",
        },
    ]


def template_question_form_fields(question: Row | None = None) -> list[Row]:
    current = question or {}
    return [
        {
            "name": "question",
            "label": "Вопрос",
            "type": "textarea",
            "required": True,
            "value": current.get("question") or "",
        },
        {
            "name": "answer",
            "label": "Ответ (необязательно)",
            "type": "textarea",
            "value": current.get("answer") or "",
        },
    ]


def save_template_form_fields(interview_id: int, default_name: str) -> list[Row]:
    return [
        {"name": "name", "label": "Название шаблона", "type": "text", "required": True, "value": default_name},
        {"name": "description", "label": "Описание", "type": "textarea", "value": ""},
    ]


# ==================== ДЕТАЛИ ИНТЕРВЬЮ ====================


def detail_info(request: Request, interview: Row) -> list[tuple[str, str]]:
    stakeholder = (
        f'<a href="{_esc(_url(request, "stakeholder_detail", id=interview["stakeholder_id"]))}">'
        f"{_esc(interview['last_name'])} {_esc(interview['first_name'])}</a>"
    )
    return [
        ("Интервью", f"#{interview['id']}"),
        ("Стейкхолдер", stakeholder),
        ("Дата-время", _esc(interview.get("scheduled_at") or "-")),
    ]


def qa_table(request: Request, interview_id: int, qas: list[Row], is_admin: bool) -> Row:
    rows: list[list[str]] = []
    for qa in qas:
        if is_admin:
            form_id = f"qa-{qa['id']}"
            edit_url = _esc(_url(request, "interview_qa_edit", id=qa["id"]))
            delete_url = _esc(_url(request, "interview_qa_delete", id=qa["id"]))
            rows.append(
                [
                    f'<form id="{form_id}" method="POST" action="{edit_url}">'
                    f'<input type="hidden" name="interview_id" value="{interview_id}"></form>#{qa["id"]}',
                    f'<textarea form="{form_id}" name="question" required style="width:100%; min-height:60px;">'
                    f"{_esc(qa['question'])}</textarea>",
                    f'<textarea form="{form_id}" name="answer" style="width:100%; min-height:60px;">'
                    f"{_esc(qa['answer'] or '')}</textarea>",
                    '<div style="white-space:nowrap">'
                    f'<button type="submit" form="{form_id}" class="btn btn-success">Сохранить</button> '
                    f'<a href="{delete_url}" class="btn btn-danger" '
                    f"onclick=\"return confirm('Удалить?')\">Удалить</a></div>",
                ]
            )
        else:
            rows.append(
                [
                    f"#{qa['id']}",
                    _esc(qa["question"]).replace("\n", "<br>"),
                    _esc(qa["answer"] or "-").replace("\n", "<br>"),
                    "",
                ]
            )
    return {
        "title": "Вопросы и ответы",
        "headers": ["ID", "Вопрос", "Ответ", "Действия"],
        "rows": rows,
    }


def audio_table(request: Request, audios: list[Row], is_admin: bool) -> Row:
    rows: list[list[str]] = []
    for audio in audios:
        actions = [
            _anchor(request, "interview_audio_download", "Скачать", "btn btn-primary", aid=audio["id"]),
        ]
        if is_admin:
            actions.append(_anchor(request, "interview_audio_delete", "Удалить", "btn btn-danger", aid=audio["id"]))
        player = (
            f'<audio class="player" controls preload="none" style="height:32px; vertical-align:middle;" '
            f'src="{_esc(_url(request, "interview_audio_get", aid=audio["id"]))}"></audio>'
        )
        rows.append(
            [
                str(audio["id"]),
                _esc(audio.get("original_name") or audio.get("filename")),
                player,
                " ".join(actions),
            ]
        )
    return {
        "title": "Аудиозаписи",
        "headers": ["ID", "Файл", "Прослушать", "Действия"],
        "rows": rows,
    }


def transcript_table(request: Request, interview_id: int, segments: list[Row], is_admin: bool) -> Row:
    rows: list[list[str]] = []
    for segment in segments:
        actions = ""
        if is_admin:
            actions = _anchor(
                request, "transcript_segment_delete", "Удалить", "btn btn-danger", id=interview_id, sid=segment["id"]
            )
        rows.append(
            [
                f'<a href="#" onclick="seek({segment["start_ms"]}); return false;">'
                f"{fmt_timecode(segment['start_ms'])}</a>",
                fmt_timecode(segment["end_ms"]),
                _esc(segment.get("speaker") or "-"),
                _esc(segment["text"]),
                actions,
            ]
        )
    return {
        "title": "Транскрипт (посегментные таймкоды)",
        "headers": ["Начало", "Конец", "Спикер", "Текст", "Действия"],
        "rows": rows,
    }


def detail_actions(request: Request, interview_id: int, is_admin: bool) -> str:
    actions = [_anchor(request, "interview_export", "Экспорт (Markdown)", "btn btn-success", id=interview_id)]
    if not is_admin:
        return " ".join(actions)
    actions.append(
        _anchor(request, "interview_save_as_template", "Сохранить как шаблон", "btn btn-warning", id=interview_id)
    )
    actions.append(
        _anchor(request, "interview_qa_create", "+ Добавить вопрос", "btn btn-success", interview_id=interview_id)
    )
    actions.append(
        '<button type="button" class="btn btn-danger" id="recStart" onclick="startRec()">● Записать</button>',
    )
    actions.append(
        '<button type="button" class="btn btn-secondary" id="recStop" onclick="stopRec()" '
        'style="display:none;">■ Стоп</button>',
    )
    actions.append('<span id="recStatus" class="muted" style="margin-left:6px;"></span>')
    return " ".join(actions)


def transcript_controls(request: Request, interview_id: int, is_admin: bool) -> str:
    if not is_admin:
        return ""
    transcribe_url = _esc(_url(request, "interview_transcribe", id=interview_id))
    edit_url = _esc(_url(request, "transcript_edit", id=interview_id))
    clear_url = _esc(_url(request, "transcript_clear", id=interview_id))
    return (
        f'<form method="POST" action="{transcribe_url}" '
        'onsubmit="return busy(this, \'Распознавание…\');" style="display:inline; margin-left:8px;">'
        '<button type="submit" class="btn btn-warning">Распознать (Whisper)</button></form>'
        f'<a href="{edit_url}" class="btn btn-primary" style="margin-left:6px;">Редактировать</a>'
        f'<form method="POST" action="{clear_url}" style="display:inline; margin-left:6px;">'
        '<button type="submit" class="btn btn-danger" '
        "onclick=\"return confirm('Очистить транскрипт?')\">Очистить</button></form>"
    )


def detail_context(
    request: Request,
    interview: Row,
    qas: list[Row],
    audios: list[Row],
    segments: list[Row],
    is_admin: bool,
) -> Row:
    interview_id = int(interview["id"])
    controls = transcript_controls(request, interview_id, is_admin)
    transcript = transcript_table(request, interview_id, segments, is_admin)
    if controls:
        transcript["title"] = transcript["title"] + " " + controls
    upload_url = _url(request, "interview_audio_upload", id=interview_id)
    return {
        "info": detail_info(request, interview),
        "qa_table": qa_table(request, interview_id, qas, is_admin),
        "audio_table": audio_table(request, audios, is_admin),
        "transcript_table": transcript,
        "actions": detail_actions(request, interview_id, is_admin),
        "bottom_script": _RECORD_SCRIPT.replace("__UPLOAD__", html.escape(upload_url)),
    }


def transcript_edit_context(request: Request, interview_id: int, segments: list[Row]) -> Row:
    return {
        "interview_id": interview_id,
        "action": _url(request, "transcript_segments_save", id=interview_id),
        "back_url": _url(request, "interview_detail", id=interview_id),
        "segments": [
            {
                "id": segment["id"],
                "start": fmt_timecode(segment["start_ms"]),
                "end": fmt_timecode(segment["end_ms"]),
                "speaker": segment.get("speaker") or "",
                "text": segment["text"],
            }
            for segment in segments
        ],
    }


# ==================== ДЕТАЛИ ШАБЛОНА ====================


def template_detail_context(request: Request, template: Row, questions: list[Row], is_admin: bool) -> Row:
    template_id = int(template["id"])
    rows: list[list[str]] = []
    for question in questions:
        actions = ""
        if is_admin:
            actions = " ".join(
                [
                    _anchor(
                        request, "interview_template_question_edit", "Изменить", "btn btn-primary", id=question["id"]
                    ),
                    _anchor(
                        request,
                        "interview_template_question_delete",
                        "Удалить",
                        "btn btn-danger",
                        id=question["id"],
                    ),
                ]
            )
        rows.append(
            [
                str(question["id"]),
                _esc(question["question"]),
                _esc(question.get("answer") or "-"),
                actions,
            ]
        )
    info = [
        ("Шаблон", f"#{template_id}"),
        ("Название", _esc(template["name"])),
        ("Описание", _esc(template.get("description") or "-")),
    ]
    tables = [
        {
            "title": "Вопросы",
            "headers": ["ID", "Вопрос", "Ответ", "Действия"],
            "rows": rows,
        }
    ]
    actions = ""
    if is_admin:
        actions = " ".join(
            [
                _anchor(
                    request,
                    "interview_template_question_create",
                    "+ Добавить вопрос",
                    "btn btn-success",
                    id=template_id,
                ),
                _anchor(
                    request,
                    "interview_create",
                    "Создать интервью по шаблону",
                    "btn btn-warning",
                    template_id=template_id,
                ),
            ]
        )
    return {"info": info, "tables": tables, "actions": actions}
