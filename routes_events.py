"""События."""

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

#==================== СОБЫТИЯ ====================
@app.route('/events')
def events_list():
    db = get_db()
    events = db.execute("""
        SELECT * FROM event WHERE is_deleted=0 ORDER BY occurred_at DESC
    """).fetchall()
    rows = ''.join([f'''
        <tr>
            <td>{e['id']}</td>
            <td>{e['occurred_at']}</td>
            <td>{e['description'][:60]}...</td>
            <td>{(e['decision'] or '-')[:60]}</td>
            <td>
                <a href="{url_for('event_detail', id=e['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('event_edit', id=e['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('event_delete', id=e['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for e in events])

    content = f'''
    <div class="card">
        <h2>События (вводные преподавателя)</h2>
        <a href="{url_for('event_create')}" class="btn btn-success">+ Добавить событие</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Дата/время</th><th>Описание</th><th>Решение</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='События', content=content)

@app.route('/events/create', methods=['GET', 'POST'])
def event_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO event (occurred_at, description, decision) VALUES (?, ?, ?)",
                  (request.form.get('occurred_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   request.form['description'],
                   request.form.get('decision')))
        db.commit()
        db.close()
        flash('Событие создано', 'success')
        return redirect(url_for('events_list'))

    content = f'''
    <div class="card">
        <h2>Новое событие</h2>
        <form method="POST">
            <div class="form-group">
                <label>Дата/время события</label>
                <input type="datetime-local" name="occurred_at" value="{datetime.now().strftime('%Y-%m-%dT%H:%M')}">
            </div>
            <div class="form-group">
                <label>Описание события</label>
                <textarea name="description" required placeholder="Например: форс-мажор, изменение конъюнктуры, болезнь сотрудника..."></textarea>
            </div>
            <div class="form-group">
                <label>Принятое решение</label>
                <textarea name="decision" placeholder="Как отреагировал СА"></textarea>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('events_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новое событие', content=content)

@app.route('/events/edit/<int:id>', methods=['GET', 'POST'])
def event_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE event SET occurred_at=?, description=?, decision=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form.get('occurred_at'), request.form['description'],
                   request.form.get('decision'), id))
        db.commit()
        db.close()
        flash('Событие обновлено', 'success')
        return redirect(url_for('events_list'))

    event = db.execute("SELECT * FROM event WHERE id=?", (id,)).fetchone()
    if not event:
        db.close()
        flash('Событие не найдено', 'error')
        return redirect(url_for('events_list'))
    db.close()

    occurred = event['occurred_at'].replace(' ', 'T') if event['occurred_at'] else ''

    content = f'''
    <div class="card">
        <h2>Редактировать событие</h2>
        <form method="POST">
            <div class="form-group">
                <label>Дата/время события</label>
                <input type="datetime-local" name="occurred_at" value="{occurred}">
            </div>
            <div class="form-group">
                <label>Описание события</label>
                <textarea name="description" required>{event['description']}</textarea>
            </div>
            <div class="form-group">
                <label>Принятое решение</label>
                <textarea name="decision">{event['decision'] or ''}</textarea>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('events_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать событие', content=content)

@app.route('/events/delete/<int:id>')
def event_delete(id):
    db = get_db()
    db.execute("UPDATE event SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Событие удалено', 'success')
    return redirect(url_for('events_list'))

