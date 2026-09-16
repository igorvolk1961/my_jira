"""HTML-представление домена «Артефакты СА» и пользовательских историй."""

import html
import json
from collections.abc import Mapping
from typing import Any

from fastapi import Request

from app.presentation import project_views
from app.presentation.render import render_markdown

Row = dict[str, Any]

_BPMN_CSS = (
    "bpmn/assets/diagram-js.css",
    "bpmn/assets/bpmn-js.css",
    "bpmn/assets/bpmn-font/css/bpmn-embedded.css",
)

_US_TEXTAREA = "width:100%; min-height:44px; resize:vertical; font-family:inherit;"


def _url(request: Request, name: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return "#"


def _esc(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def bpmn_head_html(request: Request) -> str:
    return "".join(f'<link rel="stylesheet" href="{_url(request, "static", path=p)}">' for p in _BPMN_CSS)


def _empty_hint(can_edit: bool, authenticated: bool, prefix: str, action: str) -> str:
    if can_edit:
        return f"{prefix} Нажмите «Изменить», чтобы {action}."
    if authenticated:
        return (
            f"{prefix} Редактирование доступно администратору и системному аналитику "
            f"(текущая роль не позволяет правку)."
        )
    return f"{prefix} Для редактирования войдите в систему (роль «Системный аналитик»)."


def artifact_actions(request: Request, artifact: Mapping[str, Any], can_edit: bool) -> str:
    if not can_edit:
        return ""
    key = artifact["key"]
    return (
        f'<a href="{_url(request, "artifact_edit", key=key)}" class="btn btn-primary">Изменить</a>'
        f'<a href="{_url(request, "artifact_clear", key=key)}" class="btn btn-danger"'
        f" onclick=\"return confirm('Очистить?')\">Очистить</a>"
    )


def _json_for_script(value: str) -> str:
    """JSON, безопасный для вставки внутрь <script> (экранирует <, >, &, ')."""
    return (
        json.dumps(value)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("'", "\\u0027")
    )


def bpmn_view_html(request: Request, content: str) -> str:
    canvas = '<div id="bpmn-canvas" style="height:560px; background:#fff; border:1px solid #ddd;"></div>'
    return (
        f"{canvas}"
        f"{bpmn_head_html(request)}"
        f'<script src="{_url(request, "static", path="bpmn/bpmn-navigated-viewer.production.min.js")}"></script>'
        "<script>\n"
        "(function() {\n"
        "    var viewer = new BpmnJS({ container: '#bpmn-canvas' });\n"
        f"    viewer.importXML({_json_for_script(content)}).catch(function(err) {{\n"
        "        document.getElementById('bpmn-canvas').innerHTML =\n"
        '            \'<p class="muted" style="padding:10px;">Не удалось отобразить диаграмму.</p>\';\n'
        "    });\n"
        "})();\n"
        "</script>"
    )


def requirements_html(
    request: Request,
    requirements: list[Row],
    project_id: int,
    next_url: str,
    preset_type_id: int | None,
    show_nfr_type: bool,
) -> str:
    def with_next(endpoint: str, **kw: Any) -> str:
        if next_url:
            kw["next"] = next_url
        return _url(request, endpoint, **kw)

    nfr_header = "<th>Тип НФТ</th>" if show_nfr_type else ""
    rows = "".join(
        [
            "<tr>"
            f"<td>{r['id']}</td>"
            f"<td>{_esc(r['type_name'])}</td>"
            + (f"<td>{_esc(r['nfr_type_name'] or '-')}</td>" if show_nfr_type else "")
            + (
                f'<td><a href="{_url(request, "stakeholder_detail", id=r["stakeholder_id"])}">'
                f"{_esc(r['last_name'] or '')} {_esc(r['first_name'] or '')}</a></td>"
                if r["stakeholder_id"]
                else "<td>-</td>"
            )
            + f"<td>{_esc((r['description'] or '')[:80])}</td>"
            f"<td>{_esc(r['priority_name'])}</td>"
            "<td>"
            f'<a href="{with_next("requirement_detail", id=r["id"])}" class="btn btn-success">Открыть</a> '
            f'<a href="{with_next("requirement_edit", id=r["id"])}" class="btn btn-primary">Изменить</a> '
            f'<a href="{with_next("requirement_delete", id=r["id"])}" class="btn btn-danger"'
            f" onclick=\"return confirm('Удалить?')\">Удалить</a>"
            "</td>"
            "</tr>"
            for r in requirements
        ]
    )

    create_kwargs: dict[str, Any] = {"project_id": project_id}
    if preset_type_id:
        create_kwargs["requirement_type_id"] = preset_type_id
    if next_url:
        create_kwargs["next"] = next_url
    add_link = _url(request, "requirement_create", **create_kwargs)

    return f"""
        <a href="{add_link}" class="btn btn-success">+ Добавить требование</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Тип</th>{nfr_header}<th>Стейкхолдер</th><th>Описание</th><th>Приоритет</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>"""


def _us_cell(label: str, inner: str, flex: str = "1 1 0") -> str:
    return (
        f'<div style="flex:{flex}; min-width:0;">'
        f'<label style="display:block; font-size:12px; color:#555; margin-bottom:2px;">{label}</label>'
        f"{inner}</div>"
    )


def _user_story_role(story: Mapping[str, Any]) -> str:
    return str(story.get("stakeholder_type_name") or story.get("role") or "…")


def user_stories_html(request: Request, project: Mapping[str, Any], data: Mapping[str, Any], can_edit: bool) -> str:
    stories: list[Row] = list(data["stories"])
    sections: list[Row] = list(data["sections"])
    types: list[Row] = list(data["types"])
    stories_by_section: dict[Any, list[Row]] = {}
    for story in stories:
        stories_by_section.setdefault(story["section_id"], []).append(story)

    def type_options(selected_id: Any) -> str:
        opts = ['<option value="">— не выбран —</option>']
        for t in types:
            sel = "selected" if t["id"] == selected_id else ""
            opts.append(f'<option value="{t["id"]}" {sel}>{html.escape(str(t["name"]))}</option>')
        return "".join(opts)

    def story_cells(identifier: str, want: str, benefit: str, selected_type_id: Any, required: bool = False) -> str:
        req = " required" if required else ""
        return (
            _us_cell(
                "ID",
                f'<textarea name="identifier" style="{_US_TEXTAREA}" placeholder="US-N (авто)">{identifier}</textarea>',
                flex="0 0 110px",
            )
            + _us_cell(
                "Как",
                f'<select name="stakeholder_type_id" style="width:100%;">{type_options(selected_type_id)}</select>',
                flex="0 0 180px",
            )
            + _us_cell(
                "Я хочу", f'<textarea name="want" style="{_US_TEXTAREA}" placeholder="я хочу…"{req}>{want}</textarea>'
            )
            + _us_cell(
                "Чтобы",
                f'<textarea name="benefit" style="{_US_TEXTAREA}" placeholder="чтобы…"{req}>{benefit}</textarea>',
            )
        )

    def handle() -> str:
        if not can_edit:
            return ""
        return (
            '<span class="us-drag" draggable="true" title="Перетащить" '
            'style="cursor:grab; color:#95a5a6; user-select:none;">⠿</span>'
        )

    def story_view(story: Row) -> str:
        if can_edit:
            cells = story_cells(
                html.escape(str(story["identifier"] or ""), quote=True),
                html.escape(str(story["want"] or "")),
                html.escape(str(story["benefit"] or "")),
                story["stakeholder_type_id"],
            )
            return f'''<form method="POST" action="{_url(request, "user_story_edit", id=story["id"])}" data-us-kind="story" data-us-id="{story["id"]}" style="display:flex; gap:10px; align-items:flex-start; border:1px solid #ddd; border-left:3px solid #3498db; border-radius:6px; padding:8px 10px; margin:6px 0; background:#fff;">
                <div style="flex:0 0 auto; padding-top:16px;">{handle()}</div>
                {cells}
                <div style="flex:0 0 auto; padding-top:16px; white-space:nowrap;">
                    <button type="submit" class="btn btn-success">Сохранить</button>
                    <a href="{_url(request, "user_story_delete", id=story["id"])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
                </div>
            </form>'''
        return f'''<div data-us-kind="story" data-us-id="{story["id"]}" style="display:flex; gap:10px; align-items:flex-start; border:1px solid #ddd; border-left:3px solid #3498db; border-radius:6px; padding:8px 10px; margin:6px 0; background:#fff;">
            <div style="flex:0 0 auto; padding-top:2px;">{handle()}</div>
            {_us_cell("ID", html.escape(str(story["identifier"] or f"US-{story['id']}")), flex="0 0 110px")}
            {_us_cell("Как", html.escape(_user_story_role(story)), flex="0 0 180px")}
            {_us_cell("Я хочу", f'<div style="white-space:pre-wrap;">{html.escape(str(story["want"] or "-"))}</div>')}
            {_us_cell("Чтобы", f'<div style="white-space:pre-wrap;">{html.escape(str(story["benefit"] or "-"))}</div>')}
        </div>'''

    def add_story_form(section_id: Any) -> str:
        if not can_edit:
            return ""
        cells = story_cells("", "", "", None, required=True)
        return f'''<details style="margin:6px 0;">
            <summary style="cursor:pointer; color:#27ae60; font-size:13px;">+ следующая история</summary>
            <form method="POST" action="{_url(request, "user_story_create")}" style="display:flex; gap:10px; align-items:flex-start; margin:6px 0; padding:8px 10px; background:#fbfbfb; border:1px dashed #ccc; border-radius:6px;">
                <input type="hidden" name="section_id" value="{section_id or ""}">
                {cells}
                <div style="flex:0 0 auto; padding-top:16px; white-space:nowrap;">
                    <button type="submit" class="btn btn-success">Добавить</button>
                </div>
            </form>
        </details>'''

    def add_section_form() -> str:
        if not can_edit:
            return ""
        return f'''<details style="margin:12px 0 4px;">
            <summary style="cursor:pointer; color:#2980b9; font-size:13px;">+ раздел</summary>
            <form method="POST" action="{_url(request, "user_story_section_create")}" style="margin:6px 0; padding:8px 10px; background:#fbfbfb; border:1px dashed #ccc; border-radius:6px;">
                {_us_cell("Название", '<input name="name" required placeholder="Название раздела" style="width:100%;">', flex="0 1 320px")}
                <div style="margin-top:6px;"><button type="submit" class="btn btn-primary">Добавить раздел</button></div>
            </form>
        </details>'''

    def render_section(section: Row) -> str:
        inner = ""
        for story in stories_by_section.get(section["id"], []):
            inner += story_view(story)
        inner += add_story_form(section["id"])
        actions = ""
        if can_edit:
            actions = (
                f'<a href="#" class="us-rename" data-edit-url="{_url(request, "user_story_section_edit", id=section["id"])}" '
                f'onclick="event.stopPropagation(); return false;" '
                f'style="margin-left:8px; font-weight:normal;">Переименовать</a>'
                f'<a href="{_url(request, "user_story_section_delete", id=section["id"])}" '
                f"onclick=\"event.stopPropagation(); return confirm('Удалить раздел?');\" "
                f'style="margin-left:8px; font-weight:normal; color:#c0392b;">Удалить</a>'
            )
        return (
            f'<details class="us-section" data-us-kind="section" data-us-id="{section["id"]}" open '
            f'style="margin:8px 0; border:1px solid #ddd; border-radius:6px; padding:6px 10px; background:#f7f9fa;">'
            f'<summary style="cursor:pointer; font-weight:bold;">{handle()} '
            f'<span class="us-sec-name">{html.escape(str(section["name"]))}</span>{actions}</summary>'
            f'<div class="us-section-body" style="margin-top:6px;">{inner}</div></details>'
        )

    body = ""
    for story in stories_by_section.get(None, []):
        body += story_view(story)
    for section in sections:
        body += render_section(section)
    body += add_section_form()
    if not stories and not sections:
        body = '<p class="muted">Разделов и историй пока нет. Добавьте раздел, затем — истории в нём.</p>'

    markdown_text = _user_stories_markdown(sections, stories)
    md_rendered = render_markdown(markdown_text)
    text_block = (
        '<div id="us-text" style="display:none; margin-top:12px;">'
        "<h3>Текст</h3>"
        '<textarea id="us-text-src" readonly style="width:100%; min-height:160px; font-family:monospace;">'
        + html.escape(markdown_text)
        + '</textarea><h3>Просмотр</h3><div class="markdown-body">'
        + md_rendered
        + "</div></div>"
    )

    tree = (
        f'<div id="us-tree" data-reorder-url="{_url(request, "user_story_reorder")}" '
        f'style="max-height:60vh; overflow-y:auto; overflow-x:hidden; padding-right:6px;">{body}</div>'
    )
    script = ""
    if can_edit:
        script = """
<script>
(function(){
  var root = document.getElementById('us-tree');
  if (!root) return;
  var drag = null;
  function owner(node){ return node && node.closest ? node.closest('[data-us-kind]') : null; }
  root.querySelectorAll('.us-drag').forEach(function(h){
    h.addEventListener('dragstart', function(e){
      drag = owner(h);
      if (!drag) return;
      e.stopPropagation();
      e.dataTransfer.effectAllowed = 'move';
      try { e.dataTransfer.setData('text/plain', drag.getAttribute('data-us-id')); } catch(_) {}
    });
    h.addEventListener('dragend', function(){ drag = null; });
  });
  root.querySelectorAll('[data-us-kind]').forEach(function(target){
    target.addEventListener('dragover', function(e){
      if (!drag || drag === target) return;
      var kd = drag.getAttribute('data-us-kind');
      var kt = target.getAttribute('data-us-kind');
      if (kd === kt || kd === 'story') e.preventDefault();
    });
    target.addEventListener('drop', function(e){
      if (!drag || drag === target) return;
      var kd = drag.getAttribute('data-us-kind');
      var kt = target.getAttribute('data-us-kind');
      e.preventDefault(); e.stopPropagation();
      if (kd === 'story') {
        if (kt === 'story') {
          var r = target.getBoundingClientRect();
          var after = (e.clientY - r.top) > r.height / 2;
          target.parentNode.insertBefore(drag, after ? target.nextSibling : target);
        } else {
          var bodyEl = target.querySelector('.us-section-body') || target;
          bodyEl.appendChild(drag);
        }
      } else if (kd === 'section' && kt === 'section') {
        var rs = target.getBoundingClientRect();
        var afterS = (e.clientY - rs.top) > rs.height / 2;
        target.parentNode.insertBefore(drag, afterS ? target.nextSibling : target);
      } else {
        return;
      }
      drag = null;
      save();
    });
  });
  root.querySelectorAll('.us-rename').forEach(function(link){
    link.addEventListener('click', function(e){
      e.preventDefault(); e.stopPropagation();
      var summary = link.closest('summary');
      var span = summary ? summary.querySelector('.us-sec-name') : null;
      if (!span || span.getAttribute('data-editing')) return;
      var old = span.textContent;
      span.setAttribute('data-editing', '1');
      var input = document.createElement('input');
      input.type = 'text';
      input.value = old;
      input.style.minWidth = '200px';
      span.textContent = '';
      span.appendChild(input);
      input.focus();
      input.select();
      var done = false;
      function finish(keep){
        if (done) return;
        done = true;
        var val = input.value.trim();
        span.textContent = (keep && val) ? val : old;
        span.removeAttribute('data-editing');
        if (keep && val && val !== old) {
          fetch(link.getAttribute('data-edit-url'), {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'name=' + encodeURIComponent(val)
          }).catch(function(){});
        }
      }
      input.addEventListener('click', function(ev){ ev.stopPropagation(); });
      input.addEventListener('keydown', function(ev){
        ev.stopPropagation();
        if (ev.key === 'Enter') { ev.preventDefault(); finish(true); }
        else if (ev.key === 'Escape') { finish(false); }
      });
      input.addEventListener('blur', function(){ finish(true); });
    });
  });
  function save(){
    var sections = [], stories = [];
    root.querySelectorAll('.us-section').forEach(function(sec){
      sections.push(sec.getAttribute('data-us-id'));
    });
    root.querySelectorAll('[data-us-kind="story"]').forEach(function(st){
      var sec = st.closest('.us-section');
      stories.push({id: st.getAttribute('data-us-id'), section_id: sec ? sec.getAttribute('data-us-id') : null});
    });
    fetch(root.getAttribute('data-reorder-url'), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sections: sections, stories: stories})
    }).catch(function(){});
  }
})();
</script>"""

    return f"{tree}{script}{text_block}"


def _user_stories_markdown(sections: list[Row], stories: list[Row]) -> str:
    by_section: dict[Any, list[Row]] = {}
    unsectioned: list[Row] = []
    for story in stories:
        if story["section_id"]:
            by_section.setdefault(story["section_id"], []).append(story)
        else:
            unsectioned.append(story)

    def story_line(story: Row) -> str:
        return (
            f"- **{story['identifier'] or 'US'}**: Как {_user_story_role(story)}, "
            f"я хочу {story['want'] or '…'}, чтобы {story['benefit'] or '…'}."
        )

    lines = ["# Пользовательские истории", ""]
    for section in sections:
        lines.append("## " + str(section["name"]))
        lines.append("")
        for story in by_section.get(section["id"], []):
            lines.append(story_line(story))
        lines.append("")
    if unsectioned:
        lines.append("## Без раздела")
        lines.append("")
        for story in unsectioned:
            lines.append(story_line(story))
        lines.append("")
    if not stories:
        lines.append("Истории не заданы.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def user_stories_header_buttons(request: Request, project: Mapping[str, Any]) -> str:
    filename = f"user_stories_{project['id']}.txt"
    return (
        '<button type="button" class="btn btn-primary" '
        "onclick=\"var p=document.getElementById('us-text'); "
        "p.style.display=(p.style.display==='block'?'none':'block');\">Показать текст</button>"
        '<button type="button" class="btn btn-success" '
        "onclick=\"var s=document.getElementById('us-text-src'); "
        "var b=new Blob([s.value],{type:'text/plain;charset=utf-8'}); "
        "var a=document.createElement('a'); a.href=URL.createObjectURL(b); "
        "a.download="
        + json.dumps(filename)
        + '; document.body.appendChild(a); a.click(); a.remove();">Скачать</button>'
    )


def artifact_body(
    request: Request,
    artifact: Mapping[str, Any],
    project: Mapping[str, Any],
    data: Mapping[str, Any],
    can_edit: bool,
    authenticated: bool,
) -> str:
    kind = data["kind"]
    if kind == "user_stories":
        return user_stories_html(request, project, data, can_edit)
    if kind == "stakeholders":
        body, _count = project_views.stakeholders_block(request, data["stakeholders"], int(project["id"]))
        return body
    if kind == "backlog":
        body, _count = project_views.stage_tree_block(request, data["tree"], int(project["id"]))
        return body
    if kind == "requirements":
        return requirements_html(
            request,
            data["requirements"],
            int(project["id"]),
            next_url=_url(request, "artifact_view", key=artifact["key"]),
            preset_type_id=data["type_id"],
            show_nfr_type=bool(data["show_nfr_type"]),
        )

    row = data["row"]
    actions = artifact_actions(request, artifact, can_edit)
    meta = f'<p class="muted" style="margin:8px 0;">Обновлено: {row["updated_at"]}</p>' if row else ""

    if kind == "bpmn":
        if row and row["content"]:
            return f"{actions}{meta}{bpmn_view_html(request, str(row['content']))}"
        hint = _empty_hint(can_edit, authenticated, "Диаграмма BPMN не заполнена.", "построить модель")
        return f'{actions}<p class="muted" style="margin:10px 0;">{hint}</p>'

    if row and row["content"]:
        rendered = render_markdown(str(row["content"]))
    else:
        hint = _empty_hint(
            can_edit, authenticated, "Артефакт не заполнен.", "добавить содержимое (поддерживается Markdown)"
        )
        rendered = f'<p class="muted" style="margin:10px 0;">{hint}</p>'
        meta = ""
    return f'{actions}{meta}<div class="markdown-body">{rendered}</div>'
