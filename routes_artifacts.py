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


def _user_stories(db, project_id):
    return db.execute("SELECT * FROM user_story WHERE project_id=? AND is_deleted=0 ORDER BY id",
                      (project_id,)).fetchall()


def _user_story_groups(stories):
    """{раздел: [истории]} с сохранением порядка; пустой раздел — в конце."""
    groups = {}
    for s in stories:
        groups.setdefault((s['section'] or '').strip(), []).append(s)
    return groups


def _user_stories_markdown(stories):
    if not stories:
        return '# Пользовательские истории\n\nИстории не заданы.\n'
    groups = _user_story_groups(stories)
    lines = ['# Пользовательские истории', '']
    for key in [k for k in groups if k] + ([''] if '' in groups else []):
        lines.append(f'## {key}' if key else '## Без раздела')
        lines.append('')
        for s in groups[key]:
            lines.append(f'- **{s["identifier"] or "US"}**: Как {s["role"] or "…"}, '
                         f'я хочу {s["want"] or "…"}, чтобы {s["benefit"] or "…"}.')
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def _user_stories_html(db, project_id):
    stories = _user_stories(db, project_id)
    can_edit = can_edit_artifacts()
    groups = _user_story_groups(stories)
    sections = [k for k in groups if k]
    datalist = '<datalist id="us-sections">' + ''.join(
        f'<option value="{html.escape(k, quote=True)}"></option>' for k in sections) + '</datalist>'

    forms = ''
    rows = ''
    if not stories:
        rows = '<tr><td colspan="5" class="muted">Истории не заданы.</td></tr>'
    for key in [k for k in groups if k] + ([''] if '' in groups else []):
        rows += f'<tr class="us-section" style="background:#ecf0f1;"><td colspan="5"><strong>{html.escape(key) if key else "Без раздела"}</strong></td></tr>'
        for s in groups[key]:
            ident = html.escape(s['identifier'] or f'US-{s["id"]}')
            if can_edit:
                fid = f'story-{s["id"]}'
                forms += f'<form id="{fid}" method="POST" action="{url_for("user_story_edit", id=s["id"])}"></form>'
                rows += f'''<tr>
                    <td class="name-cell">{ident}
                        <input name="section" form="{fid}" value="{html.escape(s['section'] or '', quote=True)}" list="us-sections" placeholder="Раздел" style="width:100%; margin-top:4px;"></td>
                    <td><input name="role" form="{fid}" value="{html.escape(s['role'] or '')}" placeholder="Как…" style="width:100%;"></td>
                    <td><input name="want" form="{fid}" value="{html.escape(s['want'] or '')}" placeholder="я хочу…" style="width:100%;"></td>
                    <td><input name="benefit" form="{fid}" value="{html.escape(s['benefit'] or '')}" placeholder="чтобы…" style="width:100%;"></td>
                    <td style="white-space:nowrap;">
                        <button type="submit" form="{fid}" class="btn btn-success">Сохранить</button>
                        <a href="{url_for('user_story_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
                    </td>
                </tr>'''
            else:
                rows += f'''<tr>
                    <td class="name-cell">{ident}</td>
                    <td>{html.escape(s['role'] or '-')}</td>
                    <td>{html.escape(s['want'] or '-')}</td>
                    <td>{html.escape(s['benefit'] or '-')}</td>
                    <td></td>
                </tr>'''

    add_form = ''
    if can_edit:
        add_form = f'''
        {datalist}
        <form method="POST" action="{url_for('user_story_create')}" style="display:flex; gap:6px; flex-wrap:wrap; margin-top:12px;">
            <input name="section" placeholder="Раздел" list="us-sections" style="flex:1; min-width:160px;">
            <input name="role" placeholder="Как…" style="flex:1; min-width:160px;" required>
            <input name="want" placeholder="я хочу…" style="flex:1; min-width:160px;" required>
            <input name="benefit" placeholder="чтобы…" style="flex:1; min-width:160px;" required>
            <button type="submit" class="btn btn-success">+ Добавить историю</button>
        </form>'''

    md = _user_stories_markdown(stories)
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

@app.route('/artifacts/user_stories/create', methods=['POST'])
def user_story_create():
    db = get_db()
    project = current_project_row(db)
    if not project:
        db.close()
        flash('Сначала выберите проект', 'error')
        return redirect(url_for('artifact_view', key='user_stories'))
    num = db.execute("""SELECT COALESCE(MAX(CAST(SUBSTR(identifier, 4) AS INTEGER)), 0) + 1
                        FROM user_story WHERE project_id=?""", (project['id'],)).fetchone()[0]
    db.execute("INSERT INTO user_story (project_id, identifier, section, role, want, benefit) VALUES (?, ?, ?, ?, ?, ?)",
               (project['id'], f'US-{num}', (request.form.get('section') or '').strip(),
                request.form.get('role'), request.form.get('want'), request.form.get('benefit')))
    db.commit()
    db.close()
    flash('История добавлена', 'success')
    return redirect(url_for('artifact_view', key='user_stories'))


@app.route('/artifacts/user_stories/edit/<int:id>', methods=['POST'])
def user_story_edit(id):
    db = get_db()
    db.execute("""UPDATE user_story SET section=?, role=?, want=?, benefit=?, updated_at=CURRENT_TIMESTAMP
                  WHERE id=? AND is_deleted=0""",
               ((request.form.get('section') or '').strip(), request.form.get('role'),
                request.form.get('want'), request.form.get('benefit'), id))
    db.commit()
    db.close()
    flash('История обновлена', 'success')
    return redirect(url_for('artifact_view', key='user_stories'))


@app.route('/artifacts/user_stories/delete/<int:id>')
def user_story_delete(id):
    db = get_db()
    db.execute("UPDATE user_story SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('История удалена', 'success')
    return redirect(url_for('artifact_view', key='user_stories'))
