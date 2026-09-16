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
    {'key': 'user_stories', 'title': 'Пользовательские истории', 'kind': 'document'},
    {'key': 'use_cases', 'title': 'Варианты использования', 'kind': 'document'},
    {'key': 'functional_requirements', 'title': 'Функциональные требования', 'kind': 'requirements',
     'req_type': 'Функциональное требование'},
    {'key': 'nonfunctional_requirements', 'title': 'Нефункциональные требования', 'kind': 'requirements',
     'req_type': 'Нефункциональное требование'},
    {'key': 'bpmn', 'title': 'Модель бизнес-процессов (BPMN)', 'kind': 'document'},
    {'key': 'state_machines', 'title': 'Диаграммы состояний', 'kind': 'document'},
    {'key': 'data_model', 'title': 'Модель данных (ER)', 'kind': 'document'},
    {'key': 'prototype', 'title': 'Прототип и навигация', 'kind': 'document'},
    {'key': 'backlog', 'title': 'Бэклог и критерии приёмки', 'kind': 'backlog'},
    {'key': 'risks', 'title': 'Риски и допущения', 'kind': 'document'},
]

ARTIFACTS_BY_KEY = {a['key']: a for a in ARTIFACTS}

_DOCUMENT_HINT = 'Артефакт не заполнен. Нажмите «Изменить», чтобы добавить содержимое (поддерживается Markdown).'

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


def _artifact_body(db, artifact, project):
    kind = artifact['kind']
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

    row = db.execute("SELECT * FROM project_artifact WHERE project_id=? AND artifact_key=? AND is_deleted=0",
                     (project['id'], artifact['key'])).fetchone()
    actions = ''
    if can_edit_artifacts():
        actions = (f'<a href="{url_for("artifact_edit", key=artifact["key"])}" class="btn btn-primary">Изменить</a>'
                   f'<a href="{url_for("artifact_clear", key=artifact["key"])}" class="btn btn-danger" '
                   f'onclick="return confirm(\'Очистить артефакт?\')">Очистить</a>')
    if row and row['content']:
        rendered = _render_markdown(row['content'])
        meta = f'<p class="muted" style="margin:8px 0;">Обновлено: {row["updated_at"] or "-"}</p>'
    else:
        rendered = f'<p class="muted" style="margin:10px 0;">{_DOCUMENT_HINT}</p>'
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
    if not artifact or artifact['kind'] != 'document':
        flash('Артефакт не найден или не поддерживает правку текста', 'error')
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
    if not artifact or artifact['kind'] != 'document':
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
