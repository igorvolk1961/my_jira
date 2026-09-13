"""Задачи и подзадачи."""

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

#==================== ЗАДАЧИ ====================
@app.route('/tasks')
def tasks_list():
    db = get_db()
    tasks = db.execute("""
        SELECT t.*, r.description as req_desc, p.name as project_name, p.id as project_id,
               ps.id as stage_id, pst.name as stage_name, tt.name as type_name,
               pr.name as priority_name, ts.name as status_name, ts.color as status_color
        FROM task t
        LEFT JOIN requirement r ON t.requirement_id = r.id
        LEFT JOIN project_stage ps ON t.stage_id = ps.id
        LEFT JOIN project_stage_type pst ON ps.stage_type_id = pst.id
        LEFT JOIN project p ON p.id = COALESCE(ps.project_id, r.project_id)
        LEFT JOIN task_type tt ON t.task_type_id = tt.id
        JOIN priority pr ON t.priority_id = pr.id
        JOIN task_status ts ON t.status_id = ts.id
        WHERE t.is_deleted=0
        ORDER BY t.id DESC
    """).fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{t['id']}</td>
            <td>{f'<a href="{url_for("project_detail", id=t["project_id"])}">{t["project_name"]}</a>' if t['project_id'] else '-'}</td>
            <td>{t['description'][:40]}...</td>
            <td>{t['type_name'] or '-'}</td>
            <td>{f'<a href="{url_for("project_stage_detail", id=t["stage_id"])}">{t["stage_name"]}</a>' if t['stage_id'] else '-'}</td>
            <td>{t['priority_name']}</td>
            <td>{t['deadline'] or '-'}</td>
            <td><span class="badge" style="background: {t['status_color'] or '#95a5a6'}">{t['status_name']}</span></td>
            <td>
                <a href="{url_for('task_detail', id=t['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('task_edit', id=t['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('task_delete', id=t['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for t in tasks])

    content = f'''
    <div class="card">
        <h2>Задачи</h2>
        <a href="{url_for('task_create')}" class="btn btn-success">+ Добавить задачу</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Проект</th><th>Описание</th><th>Тип</th><th>Этап</th><th>Приоритет</th><th>Срок</th><th>Статус</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Задачи', content=content)

@app.route('/tasks/create', methods=['GET', 'POST'])
def task_create():
    db = get_db()
    if request.method == 'POST':
        stage_id = request.form.get('stage_id')
        req_id = request.form.get('requirement_id')
        ttype_id = request.form.get('task_type_id')
        if not stage_id:
            db.close()
            flash('Задача должна быть создана под этапом — выберите этап', 'error')
            origin = request.form.get('origin')
            return redirect(url_for('project_detail', id=int(origin), tab='stages')) if origin else redirect(url_for('tasks_list'))
        if not req_id:
            db.close()
            flash('Задача должна относиться к требованию — выберите требование', 'error')
            origin = request.form.get('origin')
            return redirect(url_for('project_detail', id=int(origin), tab='stages')) if origin else redirect(url_for('tasks_list'))
        if not ttype_id:
            db.close()
            flash('Выберите тип задачи', 'error')
            origin = request.form.get('origin')
            return redirect(url_for('project_detail', id=int(origin), tab='stages')) if origin else redirect(url_for('tasks_list'))
        db.execute("""INSERT INTO task (requirement_id, description, stage_id, task_type_id, priority_id, deadline, status_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (int(req_id),
                   request.form['description'],
                   int(stage_id),
                   int(ttype_id),
                   int(request.form['priority_id']),
                   request.form.get('deadline') or None,
                   int(request.form['status_id'])))
        db.commit()
        db.close()
        flash('Задача создана', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_stage_detail', id=int(stage_id)))
        return redirect(url_for('tasks_list'))

    requirements = db.execute(
        "SELECT r.id, r.description, p.name as project_name FROM requirement r JOIN project p ON r.project_id=p.id WHERE r.is_deleted=0").fetchall()
    stages = db.execute(
        "SELECT ps.id, ps.project_id, p.name as project_name, pst.name as type_name FROM project_stage ps JOIN project p ON ps.project_id=p.id JOIN project_stage_type pst ON ps.stage_type_id=pst.id WHERE ps.is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM task_status WHERE is_deleted=0").fetchall()
    task_types = db.execute("SELECT * FROM task_type WHERE is_deleted=0").fetchall()
    db.close()

    pre_stage = request.args.get('stage_id')
    origin = request.args.get('origin')
    if not pre_stage and stages:
        chosen = stages[0]
        if origin:
            for s in stages:
                if str(s['project_id']) == str(origin):
                    chosen = s
                    break
        pre_stage = str(chosen['id'])
    req_options = '<option value="">— выберите требование —</option>' + ''.join(
        [f'<option value="{r["id"]}">[{r["project_name"]}] {r["description"][:50]}</option>' for r in requirements])
    stage_options = '<option value="">— выберите этап —</option>' + ''.join(
        [f'<option value="{s["id"]}" {"selected" if str(s["id"]) == pre_stage else ""}>[{s["project_name"]}] {s["type_name"]}</option>' for s in stages])
    priority_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in priorities])
    status_options = ''.join([f'<option value="{s["id"]}">{s["name"]}</option>' for s in statuses])
    task_type_options = ''.join([f'<option value="{tt["id"]}">{tt["name"]}</option>' for tt in task_types])
    cancel_url = url_for('project_detail', id=int(origin), tab='stages') if origin else url_for('tasks_list')

    content = f'''
    <div class="card">
        <h2>Новая задача</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Требование</label>
                <select name="requirement_id" required>{req_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required></textarea>
            </div>
            <div class="form-group">
                <label>Тип задачи</label>
                <select name="task_type_id" required>{task_type_options}</select>
            </div>
            <div class="form-group">
                <label>Этап проекта</label>
                <select name="stage_id" required>{stage_options}</select>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Срок исполнения</label>
                <input type="date" name="deadline">
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новая задача', content=content)

@app.route('/tasks/edit/<int:id>', methods=['GET', 'POST'])
def task_edit(id):
    db = get_db()
    if request.method == 'POST':
        stage_id = request.form.get('stage_id')
        req_id = request.form.get('requirement_id')
        if not stage_id:
            db.close()
            flash('Задача должна быть под этапом — выберите этап', 'error')
            return redirect(url_for('tasks_list'))
        if not req_id:
            db.close()
            flash('Задача должна относиться к требованию — выберите требование', 'error')
            return redirect(url_for('tasks_list'))
        if not request.form.get('task_type_id'):
            db.close()
            flash('Выберите тип задачи', 'error')
            return redirect(url_for('tasks_list'))
        db.execute("""UPDATE task SET requirement_id=?, description=?, stage_id=?, task_type_id=?,
                     priority_id=?, deadline=?, status_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (int(req_id),
                   request.form['description'],
                   int(stage_id),
                   int(request.form['task_type_id']),
                   int(request.form['priority_id']),
                   request.form.get('deadline') or None,
                   int(request.form['status_id']), id))
        db.commit()
        db.close()
        flash('Задача обновлена', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='stages'))
        return redirect(url_for('tasks_list'))

    task = db.execute("SELECT * FROM task WHERE id=?", (id,)).fetchone()
    if not task:
        db.close()
        flash('Задача не найдена', 'error')
        return redirect(url_for('tasks_list'))
    requirements = db.execute(
        "SELECT r.id, r.description, p.name as project_name FROM requirement r JOIN project p ON r.project_id=p.id WHERE r.is_deleted=0").fetchall()
    stages = db.execute(
        "SELECT ps.id, p.name as project_name, pst.name as type_name FROM project_stage ps JOIN project p ON ps.project_id=p.id JOIN project_stage_type pst ON ps.stage_type_id=pst.id WHERE ps.is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM task_status WHERE is_deleted=0").fetchall()
    task_types = db.execute("SELECT * FROM task_type WHERE is_deleted=0").fetchall()
    db.close()

    origin = request.args.get('origin')
    cancel_url = url_for('project_detail', id=int(origin), tab='stages') if origin else url_for('tasks_list')
    req_options = '<option value="">— выберите требование —</option>' + ''.join([
                                                                       f'<option value="{r["id"]}" {"selected" if r["id"] == task["requirement_id"] else ""}>[{r["project_name"]}] {r["description"][:50]}</option>'
                                                                       for r in requirements])
    stage_options = '<option value="">— выберите этап —</option>' + ''.join([
                                                                        f'<option value="{s["id"]}" {"selected" if s["id"] == task["stage_id"] else ""}>[{s["project_name"]}] {s["type_name"]}</option>'
                                                                        for s in stages])
    priority_options = ''.join(
        [f'<option value="{p["id"]}" {"selected" if p["id"] == task["priority_id"] else ""}>{p["name"]}</option>' for p
         in priorities])
    status_options = ''.join(
        [f'<option value="{s["id"]}" {"selected" if s["id"] == task["status_id"] else ""}>{s["name"]}</option>' for s in
         statuses])
    task_type_options = ''.join(
        [f'<option value="{tt["id"]}" {"selected" if tt["id"] == task["task_type_id"] else ""}>{tt["name"]}</option>' for tt in task_types])

    content = f'''
    <div class="card">
        <h2>Редактировать задачу</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Требование</label>
                <select name="requirement_id" required>{req_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required>{task['description']}</textarea>
            </div>
            <div class="form-group">
                <label>Тип задачи</label>
                <select name="task_type_id" required>{task_type_options}</select>
            </div>
            <div class="form-group">
                <label>Этап проекта</label>
                <select name="stage_id" required>{stage_options}</select>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Срок исполнения</label>
                <input type="date" name="deadline" value="{task['deadline'] or ''}">
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать задачу', content=content)

@app.route('/tasks/delete/<int:id>')
def task_delete(id):
    db = get_db()
    db.execute("UPDATE task SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.execute("UPDATE subtask SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE parent_task_id=? AND is_deleted=0", (id,))
    db.commit()
    db.close()
    flash('Задача удалена', 'success')
    return redirect(url_for('tasks_list'))


#==================== ПОДЗАДАЧИ ====================
@app.route('/subtasks')
def subtasks_list():
    db = get_db()
    subtasks = db.execute("""
        SELECT st.*, t.description as parent_desc, pr.name as priority_name,
               ts.name as status_name, ts.color as status_color
        FROM subtask st
        JOIN task t ON st.parent_task_id = t.id
        JOIN priority pr ON st.priority_id = pr.id
        JOIN task_status ts ON st.status_id = ts.id
        WHERE st.is_deleted=0
        ORDER BY st.id DESC
    """).fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td><a href="{url_for('task_detail', id=s['parent_task_id'])}">{s['parent_desc'][:40]}...</a></td>
            <td>{s['description'][:40]}...</td>
            <td>{s['priority_name']}</td>
            <td>{s['deadline'] or '-'}</td>
            <td><span class="badge" style="background: {s['status_color'] or '#95a5a6'}">{s['status_name']}</span></td>
            <td>
                <a href="{url_for('subtask_detail', id=s['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('subtask_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('subtask_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in subtasks])

    content = f'''
    <div class="card">
        <h2>Подзадачи</h2>
        <a href="{url_for('subtask_create')}" class="btn btn-success">+ Добавить подзадачу</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Родительская задача</th><th>Описание</th><th>Приоритет</th><th>Срок</th><th>Статус</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Подзадачи', content=content)

@app.route('/subtasks/create', methods=['GET', 'POST'])
def subtask_create():
    db = get_db()
    if request.method == 'POST':
        psid = request.form.get('parent_subtask_id') or None
        ptid = request.form.get('parent_task_id')
        if psid:
            root = db.execute("SELECT parent_task_id FROM subtask WHERE id=? AND is_deleted=0", (int(psid),)).fetchone()
            if root:
                parent_task_id = root[0]
            else:
                psid = None
                parent_task_id = int(ptid) if ptid else None
        else:
            parent_task_id = int(ptid) if ptid else None
        if not parent_task_id:
            db.close()
            flash('Подзадача должна относиться к задаче', 'error')
            return redirect(url_for('subtasks_list'))
        db.execute("""INSERT INTO subtask (parent_task_id, parent_subtask_id, description, stage_id, priority_id, deadline, status_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (parent_task_id, psid,
                   request.form['description'],
                   request.form.get('stage_id') or None,
                   int(request.form['priority_id']),
                   request.form.get('deadline') or None,
                   int(request.form['status_id'])))
        db.commit()
        db.close()
        flash('Подзадача создана', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='stages'))
        return redirect(url_for('subtasks_list'))

    tasks = db.execute("SELECT * FROM task WHERE is_deleted=0").fetchall()
    subtasks = db.execute("SELECT * FROM subtask WHERE is_deleted=0").fetchall()
    stages = db.execute(
        "SELECT ps.id, p.name as project_name, pst.name as type_name FROM project_stage ps JOIN project p ON ps.project_id=p.id JOIN project_stage_type pst ON ps.stage_type_id=pst.id WHERE ps.is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM task_status WHERE is_deleted=0").fetchall()

    pre_task = request.args.get('parent_task_id')
    pre_psub = request.args.get('parent_subtask_id')
    origin = request.args.get('origin')
    root_task = pre_task
    pre_stage = None
    if pre_psub:
        r = db.execute("SELECT parent_task_id, stage_id FROM subtask WHERE id=? AND is_deleted=0", (int(pre_psub),)).fetchone()
        if r:
            root_task = str(r[0])
            pre_stage = r['stage_id']
    elif pre_task:
        r = db.execute("SELECT stage_id FROM task WHERE id=? AND is_deleted=0", (int(pre_task),)).fetchone()
        if r:
            pre_stage = r['stage_id']
    db.close()

    task_options = ''.join([f'<option value="{t["id"]}" {"selected" if str(t["id"]) == root_task else ""}>{t["id"]}. {t["description"][:50]}</option>' for t in tasks])
    subtask_options = '<option value="">— нет, подзадача напрямую от задачи —</option>' + ''.join(
        [f'<option value="{s["id"]}" {"selected" if str(s["id"]) == pre_psub else ""}>{s["id"]}. {s["description"][:50]}</option>' for s in subtasks])
    stage_options = '<option value="">Не выбран</option>' + ''.join(
        [f'<option value="{s["id"]}" {"selected" if s["id"] == pre_stage else ""}>[{s["project_name"]}] {s["type_name"]}</option>' for s in stages])
    priority_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in priorities])
    status_options = ''.join([f'<option value="{s["id"]}">{s["name"]}</option>' for s in statuses])
    cancel_url = url_for('project_detail', id=int(origin), tab='stages') if origin else url_for('subtasks_list')

    content = f'''
    <div class="card">
        <h2>Новая подзадача</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Родительская подзадача</label>
                <select name="parent_subtask_id">{subtask_options}</select>
            </div>
            <div class="form-group">
                <label>Родительская задача</label>
                <select name="parent_task_id" required>{task_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required></textarea>
            </div>
            <div class="form-group">
                <label>Этап проекта</label>
                <select name="stage_id">{stage_options}</select>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Срок исполнения</label>
                <input type="date" name="deadline">
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новая подзадача', content=content)

@app.route('/subtasks/edit/<int:id>', methods=['GET', 'POST'])
def subtask_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("""UPDATE subtask SET parent_task_id=?, description=?, stage_id=?,
                     priority_id=?, deadline=?, status_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (int(request.form['parent_task_id']),
                   request.form['description'],
                   request.form.get('stage_id') or None,
                   int(request.form['priority_id']),
                   request.form.get('deadline') or None,
                   int(request.form['status_id']), id))
        db.commit()
        db.close()
        flash('Подзадача обновлена', 'success')
        return redirect(url_for('subtasks_list'))

    subtask = db.execute("SELECT * FROM subtask WHERE id=?", (id,)).fetchone()
    if not subtask:
        db.close()
        flash('Подзадача не найдена', 'error')
        return redirect(url_for('subtasks_list'))
    tasks = db.execute("SELECT * FROM task WHERE is_deleted=0").fetchall()
    stages = db.execute(
        "SELECT ps.id, p.name as project_name, pst.name as type_name FROM project_stage ps JOIN project p ON ps.project_id=p.id JOIN project_stage_type pst ON ps.stage_type_id=pst.id WHERE ps.is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM task_status WHERE is_deleted=0").fetchall()
    db.close()

    task_options = ''.join([
                               f'<option value="{t["id"]}" {"selected" if t["id"] == subtask["parent_task_id"] else ""}>{t["id"]}. {t["description"][:50]}</option>'
                               for t in tasks])
    stage_options = '<option value="">Не выбран</option>' + ''.join([
                                                                        f'<option value="{s["id"]}" {"selected" if s["id"] == subtask["stage_id"] else ""}>[{s["project_name"]}] {s["type_name"]}</option>'
                                                                        for s in stages])
    priority_options = ''.join(
        [f'<option value="{p["id"]}" {"selected" if p["id"] == subtask["priority_id"] else ""}>{p["name"]}</option>' for
         p in priorities])
    status_options = ''.join(
        [f'<option value="{s["id"]}" {"selected" if s["id"] == subtask["status_id"] else ""}>{s["name"]}</option>' for s
         in statuses])

    content = f'''
    <div class="card">
        <h2>Редактировать подзадачу</h2>
        <form method="POST">
            <div class="form-group">
                <label>Родительская задача</label>
                <select name="parent_task_id" required>{task_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required>{subtask['description']}</textarea>
            </div>
            <div class="form-group">
                <label>Этап проекта</label>
                <select name="stage_id">{stage_options}</select>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Срок исполнения</label>
                <input type="date" name="deadline" value="{subtask['deadline'] or ''}">
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('subtasks_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать подзадачу', content=content)

@app.route('/subtasks/delete/<int:id>')
def subtask_delete(id):
    db = get_db()
    _soft_delete_subtask_tree(db, id)
    db.commit()
    db.close()
    flash('Подзадача удалена', 'success')
    return redirect(url_for('subtasks_list'))

