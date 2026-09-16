"""Требования."""

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
    safe_next,
    secure_filename,
    send_file,
    session,
    shutil,
    sqlite3,
    sync_stakeholder_for_employee,
    url_for,
)

#==================== ТРЕБОВАНИЯ ====================

@app.route('/requirements')
def requirements_list():
    db = get_db()
    requirements = db.execute("""
        SELECT r.*, p.name as project_name, s.last_name, s.first_name,
               rt.name as type_name, pr.name as priority_name
        FROM requirement r
        JOIN project p ON r.project_id = p.id
        LEFT JOIN stakeholder s ON r.stakeholder_id = s.id
        JOIN requirement_type rt ON r.requirement_type_id = rt.id
        JOIN priority pr ON r.priority_id = pr.id
        WHERE r.is_deleted=0
        ORDER BY r.id DESC
    """).fetchall()


    rows = ''.join([f'''
           <tr>
                <td>{r['id']}</td>
                <td><a href="{url_for('project_detail', id=r['project_id'])}">{r['project_name']}</a></td>
                <td>{f'<a href="{url_for("stakeholder_detail", id=r["stakeholder_id"])}">{r["last_name"]} {r["first_name"]}</a>' if r['stakeholder_id'] else '-'}</td>
                <td>{r['type_name']}</td>
                <td>{r['description'][:50]}...</td>
                <td>{r['priority_name']}</td>
                <td>
                    <a href="{url_for('requirement_detail', id=r['id'])}" class="btn btn-success">Открыть</a>
                    <a href="{url_for('requirement_edit', id=r['id'])}" class="btn btn-primary">Изменить</a>
                    <a href="{url_for('requirement_delete', id=r['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
                </td>
            </tr>
        ''' for r in requirements])

    content = f'''
       <div class="card">
           <h2>Требования</h2>
           <a href="{url_for('requirement_create')}" class="btn btn-success">+ Добавить требование</a>
           <table>
               <thead>
                   <tr><th>ID</th><th>Проект</th><th>Стейкхолдер</th><th>Тип</th><th>Описание</th><th>Приоритет</th><th>Действия</th></tr>
               </thead>
               <tbody>{rows}</tbody>
           </table>
       </div>
       '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Требования', content=content)

@app.route('/requirements/create', methods=['GET', 'POST'])
def requirement_create():
    db = get_db()
    if request.method == 'POST':
        cur = db.execute("""INSERT INTO requirement (project_id, stakeholder_id, requirement_type_id, description, priority_id, acceptance_criteria)
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (int(request.form['project_id']),
                   request.form.get('stakeholder_id') or None,
                   int(request.form['requirement_type_id']),
                   request.form['description'],
                   int(request.form['priority_id']),
                   request.form.get('acceptance_criteria')))
        new_id = cur.lastrowid
        task_id = request.form.get('task_id')
        if task_id:
            db.execute("UPDATE task SET requirement_id=? WHERE id=? AND is_deleted=0", (new_id, int(task_id)))
        db.commit()
        db.close()
        flash('Требование создано', 'success')
        next_url = request.form.get('next')
        if next_url:
            return redirect(safe_next(next_url, url_for('requirements_list')))
        if task_id:
            return redirect(url_for('task_detail', id=int(task_id)))
        return redirect(url_for('project_detail', id=int(request.form['project_id'])))

    pre_project = request.args.get('project_id')
    pre_task = request.args.get('task_id')
    pre_type = request.args.get('requirement_type_id')
    next_url = request.args.get('next')
    projects = db.execute("SELECT * FROM project WHERE is_deleted=0").fetchall()
    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    req_types = db.execute("SELECT * FROM requirement_type WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    db.close()

    project_options = ''.join([f'<option value="{p["id"]}" {"selected" if str(p["id"]) == pre_project else ""}>{p["name"]}</option>' for p in projects])
    stakeholder_options = '<option value="">Не выбран</option>' + ''.join([f'<option value="{s["id"]}">{s["last_name"]} {s["first_name"]}</option>' for s in stakeholders])
    type_options = ''.join([f'<option value="{t["id"]}" {"selected" if str(t["id"]) == pre_type else ""}>{t["name"]}</option>' for t in req_types])
    priority_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in priorities])
    if next_url:
        cancel_url = next_url
    else:
        cancel_url = url_for('task_detail', id=int(pre_task)) if pre_task else (url_for('project_detail', id=int(pre_project)) if pre_project else url_for('requirements_list'))

    content = f'''
    <div class="card">
        <h2>Новое требование</h2>
        <form method="POST">
            <input type="hidden" name="task_id" value="{pre_task or ''}">
            <input type="hidden" name="next" value="{next_url or ''}">
            <div class="form-group">
                <label>Проект</label>
                <select name="project_id" required>{project_options}</select>
            </div>
            <div class="form-group">
                <label>Стейкхолдер</label>
                <select name="stakeholder_id">{stakeholder_options}</select>
            </div>
            <div class="form-group">
                <label>Тип требования</label>
                <select name="requirement_type_id" required>{type_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required></textarea>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Критерий проверки</label>
                <textarea name="acceptance_criteria"></textarea>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новое требование', content=content)

@app.route('/requirements/edit/<int:id>', methods=['GET', 'POST'])
def requirement_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("""UPDATE requirement SET project_id=?, stakeholder_id=?, requirement_type_id=?,
                     description=?, priority_id=?, acceptance_criteria=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (int(request.form['project_id']),
                   request.form.get('stakeholder_id') or None,
                   int(request.form['requirement_type_id']),
                   request.form['description'],
                   int(request.form['priority_id']),
                   request.form.get('acceptance_criteria'), id))
        db.commit()
        db.close()
        flash('Требование обновлено', 'success')
        next_url = request.form.get('next')
        if next_url:
            return redirect(safe_next(next_url, url_for('requirements_list')))
        return redirect(url_for('requirements_list'))

    next_url = request.args.get('next')
    req = db.execute("SELECT * FROM requirement WHERE id=?", (id,)).fetchone()
    if not req:
        db.close()
        flash('Требование не найдено', 'error')
        return redirect(url_for('requirements_list'))
    projects = db.execute("SELECT * FROM project WHERE is_deleted=0").fetchall()
    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    req_types = db.execute("SELECT * FROM requirement_type WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    db.close()

    project_options = ''.join(
        [f'<option value="{p["id"]}" {"selected" if p["id"] == req["project_id"] else ""}>{p["name"]}</option>' for p in
         projects])
    stakeholder_options = '<option value="">Не выбран</option>' + ''.join([
                                                                              f'<option value="{s["id"]}" {"selected" if s["id"] == req["stakeholder_id"] else ""}>{s["last_name"]} {s["first_name"]}</option>'
                                                                              for s in stakeholders])
    type_options = ''.join(
        [f'<option value="{t["id"]}" {"selected" if t["id"] == req["requirement_type_id"] else ""}>{t["name"]}</option>'
         for t in req_types])
    priority_options = ''.join(
        [f'<option value="{p["id"]}" {"selected" if p["id"] == req["priority_id"] else ""}>{p["name"]}</option>' for p
         in priorities])

    content = f'''
    <div class="card">
        <h2>Редактировать требование</h2>
        <form method="POST">
            <input type="hidden" name="next" value="{next_url or ''}">
            <div class="form-group">
                <label>Проект</label>
                <select name="project_id" required>{project_options}</select>
            </div>
            <div class="form-group">
                <label>Стейкхолдер</label>
                <select name="stakeholder_id">{stakeholder_options}</select>
            </div>
            <div class="form-group">
                <label>Тип требования</label>
                <select name="requirement_type_id" required>{type_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required>{req['description']}</textarea>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Критерий проверки</label>
                <textarea name="acceptance_criteria">{req['acceptance_criteria'] or ''}</textarea>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{next_url or url_for('requirements_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать требование', content=content)

@app.route('/requirements/delete/<int:id>')
def requirement_delete(id):
    db = get_db()
    db.execute("UPDATE requirement SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Требование удалено', 'success')
    return redirect(safe_next(request.args.get('next'), url_for('requirements_list')))


