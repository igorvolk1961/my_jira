"""Комментарии."""

from app_core import (  # noqa: F401
    AUDIO_DIR,
    BASE_DIR,
    BASE_TEMPLATE,
    BytesIO,
    DATABASE_DIR,
    DEFAULT_DB_NAME,
    Flask,
    _comments_html,
    _covered_for_employee,
    _detail_page,
    _developer_type_id,
    _employee_effective_load,
    _employee_load_excluding,
    _employee_position_name,
    _entity_comments,
    _entity_project_id,
    _last_comment,
    _project_employee_options,
    _projected_load_after,
    _render_tables,
    _report_page,
    _reset_employee_stackholder_if_unlinked,
    _soft_delete_subtask_tree,
    _subtask_ancestors,
    app,
    backup_db,
    current_db_name,
    date,
    datetime,
    db_path_for,
    flash,
    fmt_timecode,
    get_db,
    html,
    init_db,
    json,
    jsonify,
    os,
    re,
    redirect,
    render_template_string,
    request,
    secure_filename,
    send_file,
    session,
    shutil,
    sqlite3,
    sync_stakeholder_for_employee,
    url_for,
)

#==================== КОММЕНТАРИИ ====================

@app.route('/comments/create', methods=['GET', 'POST'])
def comment_create():
    db = get_db()
    if request.method == 'POST':
        db.execute("INSERT INTO comment (entity_type, entity_id, author, text) VALUES (?, ?, ?, ?)",
                   (request.form['entity_type'], int(request.form['entity_id']),
                    request.form.get('author') or None, request.form['text']))
        db.commit()
        db.close()
        flash('Комментарий добавлен', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='stages'))
        if request.form['entity_type'] == 'task':
            return redirect(url_for('task_detail', id=int(request.form['entity_id'])))
        return redirect(url_for('subtask_detail', id=int(request.form['entity_id'])))
    etype = request.args.get('entity_type', 'task')
    eid = request.args.get('entity_id')
    origin = request.args.get('origin')
    label = '—'
    if etype == 'task' and eid:
        row = db.execute("SELECT description FROM task WHERE id=? AND is_deleted=0", (int(eid),)).fetchone()
        label = row[0] if row else '—'
    elif etype == 'subtask' and eid:
        row = db.execute("SELECT description FROM subtask WHERE id=? AND is_deleted=0", (int(eid),)).fetchone()
        label = row[0] if row else '—'
    pid = _entity_project_id(db, etype, eid) if eid else None
    executors = []
    if pid:
        executors = db.execute("SELECT e.id, e.last_name, e.first_name FROM project_employee pe JOIN employee e ON pe.employee_id=e.id WHERE pe.project_id=? AND pe.is_deleted=0 AND e.is_deleted=0 ORDER BY e.last_name", (pid,)).fetchall()
    author_options = '<option value="">— не указан —</option>' + ''.join(
        [f'<option value="{e["last_name"]} {e["first_name"]}">{e["last_name"]} {e["first_name"]}</option>' for e in executors])
    author_field = f'<select name="author">{author_options}</select>' if executors else '<input type="text" name="author">'
    type_options = ''.join([f'<option value="{v}" {"selected" if v==etype else ""}">{t}</option>' for v,t in (('task','Задача'),('subtask','Подзадача'))])
    if etype and eid:
        schema_fields = (f'<input type="hidden" name="entity_type" value="{etype}">'
                         f'<input type="hidden" name="entity_id" value="{eid}">')
    else:
        schema_fields = f'''
            <div class="form-group">
                <label>Тип</label>
                <select name="entity_type" required>{type_options}</select>
            </div>
            <div class="form-group">
                <label>ID задачи/подзадачи</label>
                <input type="number" name="entity_id" required>
            </div>'''
    db.close()
    cancel = url_for('project_detail', id=int(origin), tab='stages') if origin else url_for('tasks_list')
    entity_title = ('Задача #' + eid if etype == 'task' and eid else ('Подзадача #' + eid if etype == 'subtask' and eid else '—'))
    content = f'''
    <div class="card">
        <h2>Новый комментарий</h2>
        <div class="comment" style="margin-bottom:12px;">
            <strong>{entity_title}</strong><br>{html.escape(label)}
        </div>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            {schema_fields}
            <div class="form-group">
                <label>Автор (исполнитель проекта)</label>
                {author_field}
            </div>
            <div class="form-group">
                <label>Комментарий</label>
                <textarea name="text" required></textarea>
            </div>
            <button type="submit" class="btn btn-success">Добавить</button>
            <a href="{cancel}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый комментарий', content=content)

@app.route('/comments/delete/<int:id>')
def comment_delete(id):
    db = get_db()
    c = db.execute("SELECT * FROM comment WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if c:
        db.execute("UPDATE comment SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
        db.commit()
        origin = request.args.get('origin')
        if origin:
            db.close()
            return redirect(url_for('project_detail', id=int(origin), tab='stages'))
        eid, etype = c['entity_id'], c['entity_type']
        db.close()
        return redirect(url_for('task_detail', id=eid) if etype == 'task' else url_for('subtask_detail', id=eid))
    db.close()
    flash('Комментарий не найден', 'error')
    return redirect(url_for('tasks_list'))


