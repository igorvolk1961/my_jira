"""Этапы проекта."""

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

#==================== ЭТАПЫ ПРОЕКТА ====================
@app.route('/project_stages')
def project_stages_list():
    db = get_db()
    stages = db.execute("""
        SELECT ps.*, p.name as project_name, pst.name as type_name, pss.name as status_name, pss.color
        FROM project_stage ps
        JOIN project p ON ps.project_id = p.id
        JOIN project_stage_type pst ON ps.stage_type_id = pst.id
        JOIN project_stage_status pss ON ps.status_id = pss.id
        WHERE ps.is_deleted=0
        ORDER BY p.name, pst.sort_order
    """).fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td>{s['project_name']}</td>
            <td>{s['type_name']}</td>
            <td><span class="badge" style="background: {s['color'] or '#95a5a6'}">{s['status_name']}</span></td>
            <td>{s['planned_end'] or '-'}</td>
            <td>
                <a href="{url_for('project_stage_detail', id=s['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('project_stage_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('project_stage_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in stages])

    content = f'''
    <div class="card">
        <h2>Этапы проектов</h2>
        <a href="{url_for('project_stage_create')}" class="btn btn-success">+ Добавить этап</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Проект</th><th>Тип этапа</th><th>Статус</th><th>Плановая дата завершения</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Этапы проектов', content=content)

@app.route('/project_stages/create', methods=['GET', 'POST'])
def project_stage_create():
    db = get_db()
    if request.method == 'POST':
        db.execute("""INSERT INTO project_stage (project_id, stage_type_id, status_id, planned_end)
                     VALUES (?, ?, ?, ?)""",
                  (int(request.form['project_id']),
                   int(request.form['stage_type_id']),
                   int(request.form['status_id']),
                   request.form.get('planned_end') or None))
        db.commit()
        db.close()
        flash('Этап проекта создан', 'success')
        return redirect(url_for('project_stages_list'))

    projects = db.execute("SELECT * FROM project WHERE is_deleted=0").fetchall()
    stage_types = db.execute("SELECT * FROM project_stage_type WHERE is_deleted=0 ORDER BY sort_order").fetchall()
    stage_statuses = db.execute("SELECT * FROM project_stage_status WHERE is_deleted=0").fetchall()
    db.close()

    project_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in projects])
    type_options = ''.join([f'<option value="{t["id"]}">{t["name"]}</option>' for t in stage_types])
    status_options = ''.join([f'<option value="{s["id"]}">{s["name"]}</option>' for s in stage_statuses])

    content = f'''
    <div class="card">
        <h2>Новый этап проекта</h2>
        <form method="POST">
            <div class="form-group">
                <label>Проект</label>
                <select name="project_id" required>{project_options}</select>
            </div>
            <div class="form-group">
                <label>Тип этапа</label>
                <select name="stage_type_id" required>{type_options}</select>
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <div class="form-group">
                <label>Плановая дата завершения</label>
                <input type="date" name="planned_end">
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('project_stages_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый этап проекта', content=content)

@app.route('/project_stages/edit/<int:id>', methods=['GET', 'POST'])
def project_stage_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("""UPDATE project_stage SET project_id=?, stage_type_id=?, status_id=?,
                     planned_end=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (int(request.form['project_id']),
                   int(request.form['stage_type_id']),
                   int(request.form['status_id']),
                   request.form.get('planned_end') or None, id))
        db.commit()
        db.close()
        flash('Этап проекта обновлён', 'success')
        return redirect(url_for('project_stages_list'))
    stage = db.execute("SELECT * FROM project_stage WHERE id=?", (id,)).fetchone()
    if not stage:
        db.close()
        flash('Этап не найден', 'error')
        return redirect(url_for('project_stages_list'))
    projects = db.execute("SELECT * FROM project WHERE is_deleted=0").fetchall()
    stage_types = db.execute("SELECT * FROM project_stage_type WHERE is_deleted=0 ORDER BY sort_order").fetchall()
    stage_statuses = db.execute("SELECT * FROM project_stage_status WHERE is_deleted=0").fetchall()
    db.close()

    project_options = ''.join(
        [f'<option value="{p["id"]}" {"selected" if p["id"] == stage["project_id"] else ""}>{p["name"]}</option>' for p
         in projects])
    type_options = ''.join(
        [f'<option value="{t["id"]}" {"selected" if t["id"] == stage["stage_type_id"] else ""}>{t["name"]}</option>' for
         t in stage_types])
    status_options = ''.join(
        [f'<option value="{s["id"]}" {"selected" if s["id"] == stage["status_id"] else ""}>{s["name"]}</option>' for s
         in stage_statuses])

    content = f'''
    <div class="card">
        <h2>Редактировать этап проекта</h2>
        <form method="POST">
            <div class="form-group">
                <label>Проект</label>
                <select name="project_id" required>{project_options}</select>
            </div>
            <div class="form-group">
                <label>Тип этапа</label>
                <select name="stage_type_id" required>{type_options}</select>
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <div class="form-group">
                <label>Плановая дата завершения</label>
                <input type="date" name="planned_end" value="{stage['planned_end'] or ''}">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('project_stages_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать этап проекта', content=content)

@app.route('/project_stages/delete/<int:id>')
def project_stage_delete(id):
    db = get_db()
    rows = db.execute("SELECT id FROM task WHERE stage_id=? AND is_deleted=0", (id,)).fetchall()
    task_ids = [r[0] for r in rows]
    if task_ids:
        ph = ','.join('?' * len(task_ids))
        db.execute(f"UPDATE subtask SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE parent_task_id IN ({ph}) AND is_deleted=0", tuple(task_ids))
        db.execute(f"UPDATE task SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id IN ({ph})", tuple(task_ids))
    db.execute("UPDATE project_stage SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Этап проекта удалён', 'success')
    return redirect(url_for('project_stages_list'))

