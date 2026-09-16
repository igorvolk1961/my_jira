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


_NBSP = '\u00a0\u00a0'


def _user_stories(db, project_id):
    return db.execute("""
        SELECT us.*, s.last_name, s.first_name, s.middle_name
        FROM user_story us
        LEFT JOIN stakeholder s ON us.stakeholder_id = s.id
        WHERE us.project_id=? AND us.is_deleted=0
        ORDER BY us.id
    """, (project_id,)).fetchall()


def _user_story_sections(db, project_id):
    return db.execute("SELECT * FROM user_story_section WHERE project_id=? AND is_deleted=0 ORDER BY id",
                      (project_id,)).fetchall()


def _section_tree(sections):
    """Плоский список (раздел, глубина) в порядке обхода иерархии."""
    children = {}
    for s in sections:
        children.setdefault(s['parent_id'], []).append(s)
    out = []

    def walk(parent, depth):
        for s in children.get(parent, []):
            out.append((s, depth))
            walk(s['id'], depth + 1)

    walk(None, 0)
    seen = {s['id'] for s, _ in out}
    for s in sections:
        if s['id'] not in seen:
            out.append((s, 0))
    return out


def _user_story_role(st):
    name = ' '.join(x for x in (st['last_name'], st['first_name'], st['middle_name']) if x)
    return name or (st['role'] or '…')


def _stakeholder_pool(db, project_id):
    ids = {r['stakeholder_id'] for r in db.execute(
        "SELECT stakeholder_id FROM project_stakeholder WHERE project_id=? AND is_deleted=0", (project_id,))}
    proj = db.execute("SELECT main_stakeholder_id FROM project WHERE id=?", (project_id,)).fetchone()
    if proj and proj['main_stakeholder_id']:
        ids.add(proj['main_stakeholder_id'])
    if ids:
        ph = ','.join('?' * len(ids))
        return db.execute(f"SELECT * FROM stakeholder WHERE is_deleted=0 AND id IN ({ph}) ORDER BY last_name",
                          tuple(ids)).fetchall()
    return db.execute("SELECT * FROM stakeholder WHERE is_deleted=0 ORDER BY last_name").fetchall()


def _stakeholder_select_options(stakeholders, selected_id):
    opts = ['<option value="">— выберите стейкхолдера —</option>']
    for s in stakeholders:
        name = ' '.join(x for x in (s['last_name'], s['first_name']) if x)
        sel = 'selected' if s['id'] == selected_id else ''
        opts.append(f'<option value="{s["id"]}" {sel}>{html.escape(name)}</option>')
    return ''.join(opts)


def _user_stories_markdown(sections, stories):
    by_section = {}
    unsectioned = []
    for st in stories:
        if st['section_id']:
            by_section.setdefault(st['section_id'], []).append(st)
        else:
            unsectioned.append(st)
    children = {}
    for s in sections:
        children.setdefault(s['parent_id'], []).append(s)

    def story_line(st):
        return (f'- **{st["identifier"] or "US"}**: Как {_user_story_role(st)}, '
                f'я хочу {st["want"] or "…"}, чтобы {st["benefit"] or "…"}.')

    lines = ['# Пользовательские истории', '']

    def render(sec, depth):
        lines.append('#' * min(depth + 2, 6) + ' ' + sec['name'])
        lines.append('')
        for st in by_section.get(sec['id'], []):
            lines.append(story_line(st))
        if by_section.get(sec['id']):
            lines.append('')
        for child in children.get(sec['id'], []):
            render(child, depth + 1)

    for root in children.get(None, []):
        render(root, 0)
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


def _user_stories_html(db, project_id):
    stories = _user_stories(db, project_id)
    sections = _user_story_sections(db, project_id)
    ordered = _section_tree(sections)
    children = {}
    for s in sections:
        children.setdefault(s['parent_id'], []).append(s)
    stakeholders = _stakeholder_pool(db, project_id)
    types = db.execute("SELECT * FROM stakeholder_type WHERE is_deleted=0 ORDER BY id").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0 ORDER BY weight").fetchall()
    can_edit = can_edit_artifacts()

    def section_options(selected_id=None, exclude_id=None):
        opts = ['<option value="">— корневой —</option>']
        for sec, depth in ordered:
            if exclude_id and sec['id'] == exclude_id:
                continue
            sel = 'selected' if sec['id'] == selected_id else ''
            opts.append(f'<option value="{sec["id"]}" {sel}>{_NBSP * depth}{html.escape(sec["name"])}</option>')
        return ''.join(opts)

    stories_by_section = {}
    for st in stories:
        stories_by_section.setdefault(st['section_id'], []).append(st)

    forms = ''
    rows = ''

    def story_rows(sid):
        nonlocal forms
        out = ''
        for st in stories_by_section.get(sid, []):
            ident = html.escape(st['identifier'] or f'US-{st["id"]}')
            if can_edit:
                fid = f'story-{st["id"]}'
                forms += f'<form id="{fid}" method="POST" action="{url_for("user_story_edit", id=st["id"])}"></form>'
                out += f'''<tr>
                    <td class="name-cell"><input name="identifier" form="{fid}" value="{html.escape(st['identifier'] or '', quote=True)}" placeholder="US-N" style="width:100%;"></td>
                    <td><select name="stakeholder_id" form="{fid}">{_stakeholder_select_options(stakeholders, st["stakeholder_id"])}</select>
                        <input name="role" form="{fid}" value="{html.escape(st['role'] or '', quote=True)}" placeholder="или текст роли" style="width:100%; margin-top:4px;"></td>
                    <td><input name="want" form="{fid}" value="{html.escape(st['want'] or '')}" placeholder="я хочу…" style="width:100%;"></td>
                    <td><input name="benefit" form="{fid}" value="{html.escape(st['benefit'] or '')}" placeholder="чтобы…" style="width:100%;"></td>
                    <td style="white-space:nowrap;">
                        <button type="submit" form="{fid}" class="btn btn-success">Сохранить</button>
                        <a href="{url_for('user_story_delete', id=st['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
                    </td>
                </tr>'''
            else:
                out += f'''<tr>
                    <td class="name-cell">{ident}</td>
                    <td>{html.escape(_user_story_role(st))}</td>
                    <td>{html.escape(st['want'] or '-')}</td>
                    <td>{html.escape(st['benefit'] or '-')}</td>
                    <td></td>
                </tr>'''
        return out

    rendered_sections = set()

    def section_block(sec, depth):
        nonlocal rows
        rendered_sections.add(sec['id'])
        rows += (f'<tr class="us-section" style="background:#ecf0f1;"><td colspan="5">'
                 f'<strong>{_NBSP * depth}{html.escape(sec["name"])}</strong></td></tr>')
        rows += story_rows(sec['id'])
        for child in children.get(sec['id'], []):
            section_block(child, depth + 1)

    for sec, depth in ordered:
        if sec['id'] not in rendered_sections:
            section_block(sec, depth)
    rows += story_rows(None)
    if not stories:
        rows += '<tr><td colspan="5" class="muted">Истории не заданы.</td></tr>'

    sections_editor = ''
    if can_edit:
        sec_rows = ''
        for sec, depth in ordered:
            fid = f'section-{sec["id"]}'
            forms += f'<form id="{fid}" method="POST" action="{url_for("user_story_section_edit", id=sec["id"])}"></form>'
            sec_rows += f'''<tr>
                <td>{_NBSP * depth}{html.escape(sec['name'])}</td>
                <td><input name="name" form="{fid}" value="{html.escape(sec['name'], quote=True)}" style="width:100%;"></td>
                <td><select name="parent_id" form="{fid}">{section_options(sec['parent_id'], exclude_id=sec['id'])}</select></td>
                <td style="white-space:nowrap;">
                    <button type="submit" form="{fid}" class="btn btn-success">Сохранить</button>
                    <a href="{url_for('user_story_section_delete', id=sec['id'])}" class="btn btn-danger" onclick="return confirm('Удалить раздел?')">Удалить</a>
                </td>
            </tr>'''
        add_section = f'''<form method="POST" action="{url_for('user_story_section_create')}" style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:8px;">
            <input name="name" placeholder="Название раздела" required style="flex:1; min-width:160px;">
            <select name="parent_id">{section_options()}</select>
            <button type="submit" class="btn btn-success">+ Раздел</button>
        </form>'''
        sections_editor = (f'<details style="margin-bottom:12px;"><summary style="cursor:pointer; font-weight:bold;">'
                           f'Разделы ({len(sections)})</summary><div style="margin-top:10px;">{add_section}'
                           f'<table><thead><tr><th>Раздел</th><th>Название</th><th>Родитель</th><th>Действия</th></tr></thead>'
                           f'<tbody>{sec_rows or "<tr><td colspan=4 class=\"muted\">Разделов нет</td></tr>"}</tbody></table>'
                           f'</div></details>')

    add_form = ''
    if can_edit:
        type_options = ''.join(f'<option value="{t["id"]}">{html.escape(t["name"])}</option>' for t in types)
        priority_options = ''.join(f'<option value="{p["weight"]}">{html.escape(p["name"])}</option>' for p in priorities)
        add_form = f'''
        <form method="POST" action="{url_for('user_story_create')}" style="display:flex; gap:6px; flex-wrap:wrap; margin-top:12px;">
            <input name="identifier" placeholder="US-N (авто)" style="flex:0 0 120px;">
            <select name="section_id" style="flex:1; min-width:160px;">{section_options()}</select>
            <select name="stakeholder_id" style="flex:1; min-width:180px;">{_stakeholder_select_options(stakeholders, None)}</select>
            <input name="role" placeholder="или текст роли" style="flex:1; min-width:140px;">
            <input name="want" placeholder="я хочу…" required style="flex:1; min-width:140px;">
            <input name="benefit" placeholder="чтобы…" required style="flex:1; min-width:140px;">
            <button type="submit" class="btn btn-success">+ Добавить историю</button>
        </form>
        <details style="margin-top:6px;"><summary style="cursor:pointer;">+ Новый стейкхолдер</summary>
            <form method="POST" action="{url_for('user_story_stakeholder_create')}" style="display:flex; gap:6px; flex-wrap:wrap; margin-top:8px;">
                <input name="last_name" placeholder="Фамилия" required>
                <input name="first_name" placeholder="Имя" required>
                <input name="middle_name" placeholder="Отчество">
                <select name="type_id">{type_options}</select>
                <select name="priority">{priority_options}</select>
                <button type="submit" class="btn btn-primary">Создать стейкхолдера</button>
            </form>
        </details>'''

    md = _user_stories_markdown(sections, stories)
    md_rendered = _render_markdown(md)
    toggle = ('<button type="button" class="btn btn-primary" '
              'onclick="var p=document.getElementById(\'us-markdown\'); '
              'p.style.display = (p.style.display === \'block\' ? \'none\' : \'block\');">Показать Markdown</button>'
              '<div id="us-markdown" style="display:none; margin-top:12px;">'
              '<h3>Markdown (исходник)</h3>'
              '<textarea readonly style="width:100%; min-height:160px; font-family:monospace;">'
              + html.escape(md) +
              '</textarea><h3>Просмотр</h3><div class="markdown-body">'
              + md_rendered + '</div></div>')

    return f'''
        {forms}
        {sections_editor}
        <table>
            <thead><tr><th>ID</th><th>Как…</th><th>Я хочу…</th><th>Чтобы…</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
        {add_form}
        <div style="margin-top:12px;">{toggle}</div>'''


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
    body = _artifact_body(db, artifact, project)
    db.close()
    content = f'''
    <div class="card" style="padding:12px 20px;">
        {selector}
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

_US_REDIRECT = lambda: redirect(url_for('artifact_view', key='user_stories'))  # noqa: E731


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


def _section_descendant_ids(db, project_id, root_id):
    ids = set()
    frontier = [root_id]
    while frontier:
        cur = frontier.pop()
        for r in db.execute("""SELECT id FROM user_story_section
                               WHERE project_id=? AND parent_id=? AND is_deleted=0""", (project_id, cur)):
            if r['id'] not in ids:
                ids.add(r['id'])
                frontier.append(r['id'])
    return ids


@app.route('/artifacts/user_stories/create', methods=['POST'])
def user_story_create():
    db = get_db()
    project = current_project_row(db)
    if not project:
        db.close()
        flash('Сначала выберите проект', 'error')
        return _US_REDIRECT()
    identifier = (request.form.get('identifier') or '').strip() or _next_user_story_identifier(db, project['id'])
    db.execute("""INSERT INTO user_story (project_id, section_id, identifier, stakeholder_id, role, want, benefit)
                  VALUES (?, ?, ?, ?, ?, ?, ?)""",
               (project['id'], _valid_section_id(db, project['id'], request.form.get('section_id')),
                identifier, request.form.get('stakeholder_id') or None, request.form.get('role'),
                request.form.get('want'), request.form.get('benefit')))
    db.commit()
    db.close()
    flash('История добавлена', 'success')
    return _US_REDIRECT()


@app.route('/artifacts/user_stories/edit/<int:id>', methods=['POST'])
def user_story_edit(id):
    db = get_db()
    row = db.execute("SELECT * FROM user_story WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if not row:
        db.close()
        flash('История не найдена', 'error')
        return _US_REDIRECT()
    identifier = (request.form.get('identifier') or '').strip() or row['identifier'] or f'US-{id}'
    db.execute("""UPDATE user_story SET section_id=?, identifier=?, stakeholder_id=?, role=?, want=?, benefit=?,
                  updated_at=CURRENT_TIMESTAMP WHERE id=?""",
               (_valid_section_id(db, row['project_id'], request.form.get('section_id')), identifier,
                request.form.get('stakeholder_id') or None, request.form.get('role'),
                request.form.get('want'), request.form.get('benefit'), id))
    db.commit()
    db.close()
    flash('История обновлена', 'success')
    return _US_REDIRECT()


@app.route('/artifacts/user_stories/delete/<int:id>')
def user_story_delete(id):
    db = get_db()
    db.execute("UPDATE user_story SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('История удалена', 'success')
    return _US_REDIRECT()


@app.route('/artifacts/user_stories/sections/create', methods=['POST'])
def user_story_section_create():
    db = get_db()
    project = current_project_row(db)
    name = (request.form.get('name') or '').strip()
    if not project or not name:
        db.close()
        flash('Укажите проект и название раздела', 'error')
        return _US_REDIRECT()
    parent_id = _valid_section_id(db, project['id'], request.form.get('parent_id'))
    db.execute("INSERT INTO user_story_section (project_id, parent_id, name) VALUES (?, ?, ?)",
               (project['id'], parent_id, name))
    db.commit()
    db.close()
    flash('Раздел добавлен', 'success')
    return _US_REDIRECT()


@app.route('/artifacts/user_stories/sections/edit/<int:id>', methods=['POST'])
def user_story_section_edit(id):
    db = get_db()
    sec = db.execute("SELECT * FROM user_story_section WHERE id=? AND is_deleted=0", (id,)).fetchone()
    name = (request.form.get('name') or '').strip()
    if not sec or not name:
        db.close()
        flash('Раздел не найден', 'error')
        return _US_REDIRECT()
    parent_id = _valid_section_id(db, sec['project_id'], request.form.get('parent_id'))
    if parent_id == id or (parent_id and parent_id in _section_descendant_ids(db, sec['project_id'], id)):
        db.close()
        flash('Нельзя вложить раздел в себя или своего потомка', 'error')
        return _US_REDIRECT()
    db.execute("UPDATE user_story_section SET name=?, parent_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (name, parent_id, id))
    db.commit()
    db.close()
    flash('Раздел обновлён', 'success')
    return _US_REDIRECT()


@app.route('/artifacts/user_stories/sections/delete/<int:id>')
def user_story_section_delete(id):
    db = get_db()
    sec = db.execute("SELECT * FROM user_story_section WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if not sec:
        db.close()
        flash('Раздел не найден', 'error')
        return _US_REDIRECT()
    has_children = db.execute("""SELECT 1 FROM user_story_section
                                 WHERE parent_id=? AND is_deleted=0 LIMIT 1""", (id,)).fetchone()
    has_stories = db.execute("""SELECT 1 FROM user_story
                                WHERE section_id=? AND is_deleted=0 LIMIT 1""", (id,)).fetchone()
    if has_children or has_stories:
        db.close()
        flash('Раздел не пуст: сначала перенесите или удалите вложенные разделы и истории', 'error')
        return _US_REDIRECT()
    db.execute("UPDATE user_story_section SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Раздел удалён', 'success')
    return _US_REDIRECT()


@app.route('/artifacts/user_stories/stakeholder/create', methods=['POST'])
def user_story_stakeholder_create():
    db = get_db()
    project = current_project_row(db)
    last_name = (request.form.get('last_name') or '').strip()
    first_name = (request.form.get('first_name') or '').strip()
    if not project or not (last_name and first_name):
        db.close()
        flash('Укажите фамилию и имя стейкхолдера', 'error')
        return _US_REDIRECT()
    type_id = request.form.get('type_id')
    if not type_id:
        first_type = db.execute("SELECT id FROM stakeholder_type WHERE is_deleted=0 ORDER BY id LIMIT 1").fetchone()
        type_id = first_type['id'] if first_type else None
    cur = db.execute("""INSERT INTO stakeholder (last_name, first_name, middle_name, type_id, priority)
                        VALUES (?, ?, ?, ?, ?)""",
                     (last_name, first_name, (request.form.get('middle_name') or '').strip() or None,
                      type_id, int(request.form.get('priority') or 3)))
    db.execute("INSERT OR IGNORE INTO project_stakeholder (project_id, stakeholder_id) VALUES (?, ?)",
               (project['id'], cur.lastrowid))
    db.commit()
    db.close()
    flash('Стейкхолдер создан и добавлен к проекту', 'success')
    return _US_REDIRECT()
