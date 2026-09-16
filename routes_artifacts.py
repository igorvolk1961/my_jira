"""Артефакты системного аналитика (по проекту)."""

from app_core import (  # noqa: F401
    BASE_TEMPLATE,
    _project_requirements_html,
    _project_stage_tree_html,
    _project_stakeholders_html,
    _render_markdown,
    app,
    can_edit_artifacts,
    current_project_row,
    current_user,
    flash,
    get_db,
    html,
    json,
    jsonify,
    project_selector_html,
    redirect,
    render_template_string,
    request,
    safe_next,
    session,
    url_for,
)

# ==================== РЕЕСТР АРТЕФАКТОВ ====================

ARTIFACTS = [
    {'key': 'vision', 'title': 'Видение (Vision)', 'kind': 'document'},
    {'key': 'glossary', 'title': 'Глоссарий', 'kind': 'document'},
    {'key': 'stakeholders', 'title': 'Заинтересованные лица', 'kind': 'stakeholders'},
    {'key': 'personas', 'title': 'Персоны', 'kind': 'document'},
    {'key': 'user_stories', 'title': 'Пользовательские истории', 'kind': 'user_stories'},
    {'key': 'use_cases', 'title': 'Варианты использования', 'kind': 'document'},
    {'key': 'functional_requirements', 'title': 'Функциональные требования', 'kind': 'requirements',
     'req_type': 'Функциональное требование'},
    {'key': 'nonfunctional_requirements', 'title': 'Нефункциональные требования', 'kind': 'requirements',
     'req_type': 'Нефункциональное требование'},
    {'key': 'bpmn', 'title': 'Модель бизнес-процессов (BPMN)', 'kind': 'bpmn'},
    {'key': 'state_machines', 'title': 'Диаграммы состояний', 'kind': 'document'},
    {'key': 'data_model', 'title': 'Модель данных (ER)', 'kind': 'document'},
    {'key': 'prototype', 'title': 'Прототип и навигация', 'kind': 'document'},
    {'key': 'backlog', 'title': 'Бэклог и критерии приёмки', 'kind': 'backlog'},
    {'key': 'risks', 'title': 'Риски и допущения', 'kind': 'document'},
]

ARTIFACTS_BY_KEY = {a['key']: a for a in ARTIFACTS}

def _empty_hint(prefix, action):
    """Подсказка для пустого артефакта — с учётом прав текущего пользователя."""
    if can_edit_artifacts():
        return f'{prefix} Нажмите «Изменить», чтобы {action}.'
    if current_user():
        return (f'{prefix} Редактирование доступно администратору и системному аналитику '
                f'(текущая роль не позволяет правку).')
    return f'{prefix} Для редактирования войдите в систему (роль «Системный аналитик»).'

# ==================== ТЕКУЩИЙ ПРОЕКТ ====================

@app.route('/current-project/<int:id>')
def current_project_set(id):
    db = get_db()
    row = db.execute("SELECT id FROM project WHERE id=? AND is_deleted=0", (id,)).fetchone()
    db.close()
    if not row:
        flash('Проект не найден', 'error')
        return redirect(url_for('index'))
    session['project_id'] = id
    return redirect(safe_next(request.args.get('next'), url_for('index')))


def _no_project_page(title):
    content = '''
    <div class="card">
        <p class="muted">Проекты не созданы. Создайте проект в разделе «Проекты», чтобы работать с артефактами.</p>
        <a href="''' + url_for('project_create') + '''" class="btn btn-success">+ Добавить проект</a>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title=title, content=content)


_BPMN_CSS = (
    'bpmn/assets/diagram-js.css',
    'bpmn/assets/bpmn-js.css',
    'bpmn/assets/bpmn-font/css/bpmn-embedded.css',
)


def _bpmn_head_html():
    return ''.join(f'<link rel="stylesheet" href="{url_for("static", filename=p)}">' for p in _BPMN_CSS)


def _artifact_row(db, artifact, project):
    return db.execute("SELECT * FROM project_artifact WHERE project_id=? AND artifact_key=? AND is_deleted=0",
                      (project['id'], artifact['key'])).fetchone()


def _artifact_actions(artifact, clear_label='Очистить'):
    if not can_edit_artifacts():
        return ''
    return (f'<a href="{url_for("artifact_edit", key=artifact["key"])}" class="btn btn-primary">Изменить</a>'
            f'<a href="{url_for("artifact_clear", key=artifact["key"])}" class="btn btn-danger" '
            f'onclick="return confirm(\'{clear_label}?\')">{clear_label}</a>')


def _user_stories(db, project_id):
    return db.execute("""
        SELECT us.*, st.name AS stakeholder_type_name
        FROM user_story us
        LEFT JOIN stakeholder_type st ON us.stakeholder_type_id = st.id
        WHERE us.project_id=? AND us.is_deleted=0
        ORDER BY us.position, us.id
    """, (project_id,)).fetchall()


def _user_story_sections(db, project_id):
    return db.execute("""SELECT * FROM user_story_section
                         WHERE project_id=? AND is_deleted=0 ORDER BY position, id""",
                      (project_id,)).fetchall()


def _user_story_role(st):
    return st['stakeholder_type_name'] or st['role'] or '…'


def _user_stories_markdown(sections, stories):
    by_section = {}
    unsectioned = []
    for st in stories:
        if st['section_id']:
            by_section.setdefault(st['section_id'], []).append(st)
        else:
            unsectioned.append(st)

    def story_line(st):
        return (f'- **{st["identifier"] or "US"}**: Как {_user_story_role(st)}, '
                f'я хочу {st["want"] or "…"}, чтобы {st["benefit"] or "…"}.')

    lines = ['# Пользовательские истории', '']
    for sec in sections:
        lines.append('## ' + sec['name'])
        lines.append('')
        for st in by_section.get(sec['id'], []):
            lines.append(story_line(st))
        lines.append('')
    if unsectioned:
        lines.append('## Без раздела')
        lines.append('')
        for st in unsectioned:
            lines.append(story_line(st))
        lines.append('')
    if not stories:
        lines.append('Истории не заданы.')
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


_US_TEXTAREA = 'width:100%; min-height:44px; resize:vertical; font-family:inherit;'


def _us_cell(label, inner, flex='1 1 0'):
    return (f'<div style="flex:{flex}; min-width:0;">'
            f'<label style="display:block; font-size:12px; color:#555; margin-bottom:2px;">{label}</label>'
            f'{inner}</div>')


def _user_stories_html(db, project_id):
    stories = _user_stories(db, project_id)
    sections = _user_story_sections(db, project_id)
    types = db.execute("SELECT * FROM stakeholder_type WHERE is_deleted=0 ORDER BY id").fetchall()
    can_edit = can_edit_artifacts()
    stories_by_section = {}
    for st in stories:
        stories_by_section.setdefault(st['section_id'], []).append(st)

    def type_options(selected_id):
        opts = ['<option value="">— не выбран —</option>']
        for t in types:
            sel = 'selected' if t['id'] == selected_id else ''
            opts.append(f'<option value="{t["id"]}" {sel}>{html.escape(t["name"])}</option>')
        return ''.join(opts)

    def story_cells(identifier, want, benefit, selected_type_id, required=False):
        req = ' required' if required else ''
        return (
            _us_cell('ID', f'<textarea name="identifier" style="{_US_TEXTAREA}" placeholder="US-N (авто)">{identifier}</textarea>', flex='0 0 110px')
            + _us_cell('Как', f'<select name="stakeholder_type_id" style="width:100%;">{type_options(selected_type_id)}</select>', flex='0 0 180px')
            + _us_cell('Я хочу', f'<textarea name="want" style="{_US_TEXTAREA}" placeholder="я хочу…"{req}>{want}</textarea>')
            + _us_cell('Чтобы', f'<textarea name="benefit" style="{_US_TEXTAREA}" placeholder="чтобы…"{req}>{benefit}</textarea>')
        )

    def handle():
        if not can_edit:
            return ''
        return ('<span class="us-drag" draggable="true" title="Перетащить" '
                'style="cursor:grab; color:#95a5a6; user-select:none;">⠿</span>')

    def story_view(st):
        if can_edit:
            cells = story_cells(html.escape(st['identifier'] or '', quote=True), html.escape(st['want'] or ''),
                                html.escape(st['benefit'] or ''), st['stakeholder_type_id'])
            return f'''<form method="POST" action="{url_for('user_story_edit', id=st['id'])}" data-us-kind="story" data-us-id="{st['id']}" style="display:flex; gap:10px; align-items:flex-start; border:1px solid #ddd; border-left:3px solid #3498db; border-radius:6px; padding:8px 10px; margin:6px 0; background:#fff;">
                <div style="flex:0 0 auto; padding-top:16px;">{handle()}</div>
                {cells}
                <div style="flex:0 0 auto; padding-top:16px; white-space:nowrap;">
                    <button type="submit" class="btn btn-success">Сохранить</button>
                    <a href="{url_for('user_story_delete', id=st['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
                </div>
            </form>'''
        return f'''<div data-us-kind="story" data-us-id="{st['id']}" style="display:flex; gap:10px; align-items:flex-start; border:1px solid #ddd; border-left:3px solid #3498db; border-radius:6px; padding:8px 10px; margin:6px 0; background:#fff;">
            <div style="flex:0 0 auto; padding-top:2px;">{handle()}</div>
            {_us_cell('ID', html.escape(st['identifier'] or f'US-{st["id"]}'), flex='0 0 110px')}
            {_us_cell('Как', html.escape(_user_story_role(st)), flex='0 0 180px')}
            {_us_cell('Я хочу', f'<div style="white-space:pre-wrap;">{html.escape(st["want"] or "-")}</div>')}
            {_us_cell('Чтобы', f'<div style="white-space:pre-wrap;">{html.escape(st["benefit"] or "-")}</div>')}
        </div>'''

    def add_story_form(section_id):
        if not can_edit:
            return ''
        cells = story_cells('', '', '', None, required=True)
        return f'''<details style="margin:6px 0;">
            <summary style="cursor:pointer; color:#27ae60; font-size:13px;">+ следующая история</summary>
            <form method="POST" action="{url_for('user_story_create')}" style="display:flex; gap:10px; align-items:flex-start; margin:6px 0; padding:8px 10px; background:#fbfbfb; border:1px dashed #ccc; border-radius:6px;">
                <input type="hidden" name="section_id" value="{section_id or ''}">
                {cells}
                <div style="flex:0 0 auto; padding-top:16px; white-space:nowrap;">
                    <button type="submit" class="btn btn-success">Добавить</button>
                </div>
            </form>
        </details>'''

    def add_section_form():
        if not can_edit:
            return ''
        return f'''<details style="margin:12px 0 4px;">
            <summary style="cursor:pointer; color:#2980b9; font-size:13px;">+ раздел</summary>
            <form method="POST" action="{url_for('user_story_section_create')}" style="margin:6px 0; padding:8px 10px; background:#fbfbfb; border:1px dashed #ccc; border-radius:6px;">
                {_us_cell('Название', '<input name="name" required placeholder="Название раздела" style="width:100%;">', flex='0 1 320px')}
                <div style="margin-top:6px;"><button type="submit" class="btn btn-primary">Добавить раздел</button></div>
            </form>
        </details>'''

    def render_section(sec):
        inner = ''
        for st in stories_by_section.get(sec['id'], []):
            inner += story_view(st)
        inner += add_story_form(sec['id'])
        actions = ''
        if can_edit:
            actions = (f'<a href="#" class="us-rename" data-edit-url="{url_for("user_story_section_edit", id=sec["id"])}" '
                       f'onclick="event.stopPropagation(); return false;" '
                       f'style="margin-left:8px; font-weight:normal;">Переименовать</a>'
                       f'<a href="{url_for("user_story_section_delete", id=sec["id"])}" '
                       f'onclick="event.stopPropagation(); return confirm(\'Удалить раздел?\');" '
                       f'style="margin-left:8px; font-weight:normal; color:#c0392b;">Удалить</a>')
        return (f'<details class="us-section" data-us-kind="section" data-us-id="{sec["id"]}" open '
                f'style="margin:8px 0; border:1px solid #ddd; border-radius:6px; padding:6px 10px; background:#f7f9fa;">'
                f'<summary style="cursor:pointer; font-weight:bold;">{handle()} '
                f'<span class="us-sec-name">{html.escape(sec["name"])}</span>{actions}</summary>'
                f'<div class="us-section-body" style="margin-top:6px;">{inner}</div></details>')

    body = ''
    for st in stories_by_section.get(None, []):
        body += story_view(st)
    for sec in sections:
        body += render_section(sec)
    body += add_section_form()
    if not stories and not sections:
        body = '<p class="muted">Разделов и историй пока нет. Добавьте раздел, затем — истории в нём.</p>'

    md = _user_stories_markdown(sections, stories)
    md_rendered = _render_markdown(md)
    text_block = ('<div id="us-text" style="display:none; margin-top:12px;">'
                  '<h3>Текст</h3>'
                  '<textarea id="us-text-src" readonly style="width:100%; min-height:160px; font-family:monospace;">'
                  + html.escape(md) +
                  '</textarea><h3>Просмотр</h3><div class="markdown-body">'
                  + md_rendered + '</div></div>')

    tree = (f'<div id="us-tree" data-reorder-url="{url_for("user_story_reorder")}" '
            f'style="max-height:60vh; overflow-y:auto; overflow-x:hidden; padding-right:6px;">{body}</div>')
    script = ''
    if can_edit:
        script = '''
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
</script>'''

    return f'''{tree}{script}{text_block}'''


def _artifact_body(db, artifact, project):
    kind = artifact['kind']
    if kind == 'user_stories':
        return _user_stories_html(db, project['id'])
    if kind == 'stakeholders':
        body, _count = _project_stakeholders_html(db, project['id'])
        return body
    if kind == 'backlog':
        body, _count = _project_stage_tree_html(db, project['id'])
        return body
    if kind == 'requirements':
        type_row = db.execute("SELECT id FROM requirement_type WHERE lower(name)=lower(?) AND is_deleted=0",
                              (artifact['req_type'],)).fetchone()
        type_id = type_row['id'] if type_row else None
        body, _count = _project_requirements_html(
            db, project['id'], type_id=type_id,
            next_url=url_for('artifact_view', key=artifact['key']), preset_type_id=type_id,
            show_nfr_type=(artifact['key'] == 'nonfunctional_requirements'))
        return body

    row = _artifact_row(db, artifact, project)
    actions = _artifact_actions(artifact)
    meta = f'<p class="muted" style="margin:8px 0;">Обновлено: {row["updated_at"]}</p>' if row else ''

    if kind == 'bpmn':
        if row and row['content']:
            canvas = '<div id="bpmn-canvas" style="height:560px; background:#fff; border:1px solid #ddd;"></div>'
            script = f'''{_bpmn_head_html()}
            <script src="{url_for('static', filename='bpmn/bpmn-navigated-viewer.production.min.js')}"></script>
            <script>
            (function() {{
                var viewer = new BpmnJS({{ container: '#bpmn-canvas' }});
                viewer.importXML({json.dumps(row['content'])}).catch(function(err) {{
                    document.getElementById('bpmn-canvas').innerHTML =
                        '<p class="muted" style="padding:10px;">Не удалось отобразить диаграмму.</p>';
                }});
            }})();
            </script>'''
            return f'{actions}{meta}{canvas}{script}'
        hint = _empty_hint('Диаграмма BPMN не заполнена.', 'построить модель')
        return f'''{actions}<p class="muted" style="margin:10px 0;">{hint}</p>'''

    if row and row['content']:
        rendered = _render_markdown(row['content'])
    else:
        hint = _empty_hint('Артефакт не заполнен.', 'добавить содержимое (поддерживается Markdown)')
        rendered = f'<p class="muted" style="margin:10px 0;">{hint}</p>'
        meta = ''
    return f'''{actions}{meta}<div class="markdown-body">{rendered}</div>'''


def _user_stories_header_buttons(project):
    """Кнопки «Показать текст» и «Скачать» для шапки страницы."""
    filename = f'user_stories_{project["id"]}.txt'
    return (
        '<button type="button" class="btn btn-primary" '
        'onclick="var p=document.getElementById(\'us-text\'); '
        'p.style.display=(p.style.display===\'block\'?\'none\':\'block\');">Показать текст</button>'
        '<button type="button" class="btn btn-success" '
        'onclick="var s=document.getElementById(\'us-text-src\'); '
        'var b=new Blob([s.value],{type:\'text/plain;charset=utf-8\'}); '
        'var a=document.createElement(\'a\'); a.href=URL.createObjectURL(b); '
        'a.download=' + json.dumps(filename) + '; document.body.appendChild(a); a.click(); a.remove();">Скачать</button>'
    )


@app.route('/artifacts/<key>')
def artifact_view(key):
    artifact = ARTIFACTS_BY_KEY.get(key)
    if not artifact:
        flash('Артефакт не найден', 'error')
        return redirect(url_for('index'))
    db = get_db()
    project = current_project_row(db)
    if not project:
        db.close()
        return _no_project_page(artifact['title'])
    selector = project_selector_html(db, project['id'], next_url=url_for('artifact_view', key=key))
    header_buttons = _user_stories_header_buttons(project) if artifact['kind'] == 'user_stories' else ''
    body = _artifact_body(db, artifact, project)
    db.close()
    content = f'''
    <div class="card" style="padding:12px 20px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
        {selector}
        {header_buttons}
    </div>
    <div class="card">
        <h2>{html.escape(artifact['title'])}</h2>
        <p class="muted" style="margin:6px 0 12px;">Проект: {html.escape(project['name'])}</p>
        {body}
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title=artifact['title'], content=content)


@app.route('/artifacts/<key>/edit', methods=['GET', 'POST'])
def artifact_edit(key):
    artifact = ARTIFACTS_BY_KEY.get(key)
    if not artifact or artifact['kind'] not in ('document', 'bpmn'):
        flash('Артефакт не найден или не поддерживает правку', 'error')
        return redirect(url_for('artifact_view', key=key))
    db = get_db()
    project = current_project_row(db)
    if not project:
        db.close()
        return _no_project_page(artifact['title'])

    if request.method == 'POST':
        content_text = request.form.get('content') or ''
        user = current_user()
        db.execute("""
            INSERT INTO project_artifact (project_id, artifact_key, content, updated_by_user_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(project_id, artifact_key) DO UPDATE SET
                content=excluded.content,
                updated_by_user_id=excluded.updated_by_user_id,
                is_deleted=0,
                updated_at=CURRENT_TIMESTAMP
        """, (project['id'], artifact['key'], content_text, user['id'] if user else None))
        db.commit()
        db.close()
        flash('Артефакт сохранён', 'success')
        return redirect(url_for('artifact_view', key=key))

    row = db.execute("SELECT content FROM project_artifact WHERE project_id=? AND artifact_key=? AND is_deleted=0",
                     (project['id'], artifact['key'])).fetchone()
    current_text = row['content'] if row and row['content'] else ''
    db.close()

    if artifact['kind'] == 'bpmn':
        content = f'''
        <div class="card">
            <h2>{html.escape(artifact['title'])}</h2>
            <p class="muted" style="margin:6px 0 12px;">Проект: {html.escape(project['name'])}</p>
            <form method="POST" id="bpmn-form">
                <input type="hidden" name="content" id="bpmn-xml">
                <button type="submit" class="btn btn-success">Сохранить</button>
                <a href="{url_for('artifact_view', key=key)}" class="btn btn-primary">Отмена</a>
            </form>
            <div id="bpmn-canvas" style="height:600px; margin-top:12px; background:#fff; border:1px solid #ddd;"></div>
        </div>
        {_bpmn_head_html()}
        <script src="{url_for('static', filename='bpmn/bpmn-modeler.production.min.js')}"></script>
        <script>
        (function() {{
            var initialXml = {json.dumps(current_text)};
            var modeler = new BpmnJS({{ container: '#bpmn-canvas' }});
            var loading = initialXml ? modeler.importXML(initialXml) : modeler.createDiagram();
            loading.catch(function(err) {{
                document.getElementById('bpmn-canvas').innerHTML =
                    '<p class="muted" style="padding:10px;">Не удалось загрузить диаграмму.</p>';
            }});
            document.getElementById('bpmn-form').addEventListener('submit', function(ev) {{
                ev.preventDefault();
                modeler.saveXML({{ format: true }}).then(function(result) {{
                    document.getElementById('bpmn-xml').value = result.xml;
                    ev.target.submit();
                }}).catch(function() {{
                    alert('Не удалось сохранить диаграмму.');
                }});
            }});
        }})();
        </script>
        '''
        return render_template_string(BASE_TEMPLATE, title='Редактировать: ' + artifact['title'], content=content)

    content = f'''
    <div class="card">
        <h2>{html.escape(artifact['title'])}</h2>
        <p class="muted" style="margin:6px 0 12px;">Проект: {html.escape(project['name'])}</p>
        <form method="POST">
            <div class="form-group">
                <label>Содержимое (Markdown)</label>
                <textarea name="content" style="min-height: 320px; font-family: monospace;">{html.escape(current_text)}</textarea>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('artifact_view', key=key)}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать: ' + artifact['title'], content=content)


@app.route('/artifacts/<key>/clear')
def artifact_clear(key):
    artifact = ARTIFACTS_BY_KEY.get(key)
    if not artifact or artifact['kind'] not in ('document', 'bpmn'):
        flash('Артефакт не найден или не поддерживает очистку', 'error')
        return redirect(url_for('artifact_view', key=key))
    db = get_db()
    project = current_project_row(db)
    if project:
        db.execute("""UPDATE project_artifact SET content=NULL, updated_at=CURRENT_TIMESTAMP
                      WHERE project_id=? AND artifact_key=?""", (project['id'], artifact['key']))
        db.commit()
    db.close()
    flash('Артефакт очищен', 'success')
    return redirect(url_for('artifact_view', key=key))


# ==================== ПОЛЬЗОВАТЕЛЬСКИЕ ИСТОРИИ ====================

def _us_redirect():
    return redirect(url_for('artifact_view', key='user_stories'))


def _next_user_story_identifier(db, project_id):
    num = db.execute("""SELECT COALESCE(MAX(CAST(SUBSTR(identifier, 4) AS INTEGER)), 0) + 1
                        FROM user_story WHERE project_id=? AND identifier LIKE 'US-%'""",
                     (project_id,)).fetchone()[0]
    return f'US-{num}'


def _valid_section_id(db, project_id, value):
    try:
        sid = int(value)
    except (TypeError, ValueError):
        return None
    row = db.execute("SELECT 1 FROM user_story_section WHERE id=? AND project_id=? AND is_deleted=0",
                     (sid, project_id)).fetchone()
    return sid if row else None


@app.route('/artifacts/user_stories/create', methods=['POST'])
def user_story_create():
    db = get_db()
    project = current_project_row(db)
    if not project:
        db.close()
        flash('Сначала выберите проект', 'error')
        return _us_redirect()
    identifier = (request.form.get('identifier') or '').strip() or _next_user_story_identifier(db, project['id'])
    position = db.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM user_story WHERE project_id=?",
                          (project['id'],)).fetchone()[0]
    db.execute("""INSERT INTO user_story (project_id, section_id, identifier, stakeholder_type_id, want, benefit, position)
                  VALUES (?, ?, ?, ?, ?, ?, ?)""",
               (project['id'], _valid_section_id(db, project['id'], request.form.get('section_id')),
                identifier, request.form.get('stakeholder_type_id') or None,
                request.form.get('want'), request.form.get('benefit'), position))
    db.commit()
    db.close()
    flash('История добавлена', 'success')
    return _us_redirect()


@app.route('/artifacts/user_stories/edit/<int:id>', methods=['POST'])
def user_story_edit(id):
    db = get_db()
    row = db.execute("SELECT * FROM user_story WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if not row:
        db.close()
        flash('История не найдена', 'error')
        return _us_redirect()
    identifier = (request.form.get('identifier') or '').strip() or row['identifier'] or f'US-{id}'
    db.execute("""UPDATE user_story SET identifier=?, stakeholder_type_id=?, want=?, benefit=?,
                  updated_at=CURRENT_TIMESTAMP WHERE id=?""",
               (identifier, request.form.get('stakeholder_type_id') or None,
                request.form.get('want'), request.form.get('benefit'), id))
    db.commit()
    db.close()
    flash('История обновлена', 'success')
    return _us_redirect()


@app.route('/artifacts/user_stories/delete/<int:id>')
def user_story_delete(id):
    db = get_db()
    db.execute("UPDATE user_story SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('История удалена', 'success')
    return _us_redirect()


@app.route('/artifacts/user_stories/sections/create', methods=['POST'])
def user_story_section_create():
    db = get_db()
    project = current_project_row(db)
    name = (request.form.get('name') or '').strip()
    if not project or not name:
        db.close()
        flash('Укажите проект и название раздела', 'error')
        return _us_redirect()
    position = db.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM user_story_section WHERE project_id=?",
                          (project['id'],)).fetchone()[0]
    db.execute("INSERT INTO user_story_section (project_id, name, position) VALUES (?, ?, ?)",
               (project['id'], name, position))
    db.commit()
    db.close()
    flash('Раздел добавлен', 'success')
    return _us_redirect()


@app.route('/artifacts/user_stories/sections/edit/<int:id>', methods=['POST'])
def user_story_section_edit(id):
    db = get_db()
    sec = db.execute("SELECT * FROM user_story_section WHERE id=? AND is_deleted=0", (id,)).fetchone()
    name = (request.form.get('name') or '').strip()
    if not sec or not name:
        db.close()
        flash('Раздел не найден или не задано название', 'error')
        return _us_redirect()
    db.execute("UPDATE user_story_section SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (name, id))
    db.commit()
    db.close()
    flash('Раздел переименован', 'success')
    return _us_redirect()


@app.route('/artifacts/user_stories/sections/delete/<int:id>')
def user_story_section_delete(id):
    db = get_db()
    sec = db.execute("SELECT * FROM user_story_section WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if not sec:
        db.close()
        flash('Раздел не найден', 'error')
        return _us_redirect()
    has_children = db.execute("SELECT 1 FROM user_story_section WHERE parent_id=? AND is_deleted=0 LIMIT 1", (id,)).fetchone()
    has_stories = db.execute("SELECT 1 FROM user_story WHERE section_id=? AND is_deleted=0 LIMIT 1", (id,)).fetchone()
    if has_children or has_stories:
        db.close()
        flash('Раздел не пуст: сначала перенесите или удалите вложенные разделы и истории', 'error')
        return _us_redirect()
    db.execute("UPDATE user_story_section SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Раздел удалён', 'success')
    return _us_redirect()


@app.route('/artifacts/user_stories/reorder', methods=['POST'])
def user_story_reorder():
    """Сохранение порядка разделов и историй после перетаскивания."""
    db = get_db()
    project = current_project_row(db)
    if not project:
        db.close()
        return jsonify(ok=False, error='no project'), 400
    data = request.get_json(silent=True) or {}
    section_ids = {s['id'] for s in _user_story_sections(db, project['id'])}

    for i, sid in enumerate(data.get('sections') or []):
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            continue
        if sid in section_ids:
            db.execute("UPDATE user_story_section SET position=? WHERE id=? AND project_id=?",
                       (i, sid, project['id']))

    for i, item in enumerate(data.get('stories') or []):
        if not isinstance(item, dict):
            continue
        try:
            story_id = int(item.get('id'))
        except (TypeError, ValueError):
            continue
        sec = item.get('section_id')
        try:
            sec = int(sec) if sec not in (None, '', 'null') else None
        except (TypeError, ValueError):
            sec = None
        if sec is not None and sec not in section_ids:
            sec = None
        db.execute("UPDATE user_story SET position=?, section_id=? WHERE id=? AND project_id=?",
                   (i, sec, story_id, project['id']))

    db.commit()
    db.close()
    return jsonify(ok=True)
