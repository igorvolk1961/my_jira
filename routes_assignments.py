"""Назначения задач."""

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

#==================== НАЗНАЧЕНИЯ ЗАДАЧ ====================
@app.route('/task_assignments')
def task_assignments_list():
    db = get_db()
    assignments = db.execute("""
        SELECT ta.*, e.last_name, e.first_name,
               CASE WHEN ta.task_kind='task' THEN (SELECT description FROM task WHERE id=ta.task_id)
                    ELSE (SELECT description FROM subtask WHERE id=ta.task_id) END as task_desc
        FROM task_assignment ta
        JOIN employee e ON ta.employee_id = e.id
        WHERE ta.is_deleted=0
        ORDER BY ta.id DESC
    """).fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{a['id']}</td>
            <td>{a['task_kind']}</td>
            <td>{f'<a href="{url_for("task_detail", id=a["task_id"])}">{a["task_desc"][:40]}...</a>' if a['task_kind'] == 'task' else f'<a href="{url_for("subtask_detail", id=a["task_id"])}">{a["task_desc"][:40]}...</a>'}</td>
            <td>{f'<a href="{url_for("employee_detail", id=a["employee_id"])}">{a["last_name"]} {a["first_name"]}</a>'}</td>
            <td>{int(a['share'] * 100)}%</td>
            <td>
                <a href="{url_for('task_assignment_detail', id=a['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('task_assignment_edit', id=a['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('task_assignment_delete', id=a['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for a in assignments])

    content = f'''
    <div class="card">
        <h2>Назначения задач</h2>
        <a href="{url_for('task_assignment_create')}" class="btn btn-success">+ Добавить назначение</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Тип</th><th>Задача</th><th>Сотрудник</th><th>Доля</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Назначения задач', content=content)

@app.route('/task_assignments/create', methods=['GET', 'POST'])
def task_assignment_create():
    db = get_db()
    if request.method == 'POST':
        task_id = int(request.form['task_id'])
        kind = request.form['task_kind']
        emp_id = int(request.form['employee_id'])
        origin = request.form.get('origin')
        if kind == 'task':
            pid = db.execute("SELECT COALESCE(ps.project_id, r.project_id) FROM task t LEFT JOIN project_stage ps ON t.stage_id=ps.id LEFT JOIN requirement r ON t.requirement_id=r.id WHERE t.id=? AND t.is_deleted=0", (task_id,)).fetchone()
        else:
            pid = db.execute("SELECT COALESCE(ps.project_id, r.project_id) FROM subtask s JOIN task t ON s.parent_task_id=t.id LEFT JOIN project_stage ps ON t.stage_id=ps.id LEFT JOIN requirement r ON t.requirement_id=r.id WHERE s.id=? AND s.is_deleted=0", (task_id,)).fetchone()
        if pid and pid[0] is not None:
            ok = db.execute("SELECT COUNT(*) FROM project_employee WHERE project_id=? AND employee_id=? AND is_deleted=0", (pid[0], emp_id)).fetchone()[0]
            if not ok:
                db.close()
                flash('Исполнитель не назначен на проект задачи', 'error')
                return redirect(url_for('project_detail', id=int(origin), tab='stages')) if origin else redirect(url_for('task_assignments_list'))
        new_share = float(request.form['share'])
        if kind == 'subtask':
            existing = db.execute("SELECT id FROM task_assignment WHERE task_id=? AND task_kind='subtask' AND is_deleted=0", (task_id,)).fetchone()
            exclude_id = existing['id'] if existing else 0
        else:
            existing = None
            exclude_id = 0
        cur_load = _projected_load_after(db, emp_id, kind, task_id, new_share, exclude_id)
        if cur_load > 1.0 + 1e-9:
            db.close()
            flash(f'Суммарная загрузка сотрудника не может превышать 100% ({round(cur_load * 100)}%)', 'error')
            return redirect(url_for('project_detail', id=int(origin), tab='stages')) if origin else redirect(url_for('task_assignments_list'))
        if kind == 'subtask' and existing:
            db.execute("UPDATE task_assignment SET employee_id=?, share=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (emp_id, new_share, existing['id']))
            db.commit()
            db.close()
            flash('Исполнитель подзадачи заменён (у подзадачи один исполнитель)', 'success')
            return redirect(url_for('project_detail', id=int(origin), tab='stages')) if origin else redirect(url_for('task_assignments_list'))
        db.execute("""INSERT INTO task_assignment (task_id, task_kind, employee_id, share)
                     VALUES (?, ?, ?, ?)""",
                  (task_id,
                   kind,
                   emp_id,
                   new_share))
        db.commit()
        db.close()
        flash('Назначение создано', 'success')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='stages'))
        return redirect(url_for('task_assignments_list'))
    tasks = db.execute("SELECT id, description FROM task WHERE is_deleted=0").fetchall()
    subtasks = db.execute("SELECT id, description FROM subtask WHERE is_deleted=0").fetchall()
    employees = db.execute("SELECT id, last_name, first_name FROM employee WHERE is_deleted=0").fetchall()
    task_proj = {}
    for t in db.execute("""
        SELECT t.id, COALESCE(ps.project_id, r.project_id) pid FROM task t
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN requirement r ON t.requirement_id=r.id
        WHERE t.is_deleted=0
    """):
        task_proj['task:' + str(t['id'])] = t['pid']
    for s in db.execute("""
        SELECT s.id, COALESCE(ps.project_id, r.project_id) pid FROM subtask s
        JOIN task t ON s.parent_task_id=t.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN requirement r ON t.requirement_id=r.id
        WHERE s.is_deleted=0
    """):
        task_proj['subtask:' + str(s['id'])] = s['pid']
    proj_emp = _project_employee_options(db)
    emp_count = {}
    for e in employees:
        cov = _covered_for_employee(db, e['id'])
        cnt = db.execute("SELECT task_id, task_kind FROM task_assignment WHERE employee_id=? AND is_deleted=0", (e['id'],)).fetchall()
        eff = [a for a in cnt if (a['task_kind'], a['task_id']) not in cov]
        emp_count[str(e['id'])] = len(eff)
    db.close()
    task_proj_json = json.dumps({k: (str(v) if v else '') for k, v in task_proj.items()})
    proj_emp_json = json.dumps({str(k): ''.join(v) for k, v in proj_emp.items()})
    emp_count_json = json.dumps(emp_count)

    pre_task = request.args.get('task_id')
    pre_kind = request.args.get('task_kind', 'task')
    origin = request.args.get('origin')

    task_options = ''.join([f'<option value="{t["id"]}" {"selected" if str(t["id"]) == pre_task and pre_kind == "task" else ""}>Задача: {t["description"][:50]}</option>' for t in tasks])
    subtask_options = ''.join(
        [f'<option value="{s["id"]}" {"selected" if str(s["id"]) == pre_task and pre_kind == "subtask" else ""}>Подзадача: {s["description"][:50]}</option>' for s in subtasks])
    employee_options = ''.join(
        [f'<option value="{e["id"]}">{e["last_name"]} {e["first_name"]}</option>' for e in employees])

    content = f'''
    <div class="card">
        <h2>Новое назначение</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Тип задачи</label>
                <select name="task_kind" required onchange="toggleTaskSelect(this.value); setEmployees()">
                    <option value="task" {"selected" if pre_kind == "task" else ""}>Задача</option>
                    <option value="subtask" {"selected" if pre_kind == "subtask" else ""}>Подзадача</option>
                </select>
            </div>
            <div class="form-group" id="task_select" style="display:{'block' if pre_kind == 'task' else 'none'}">
                <label>Задача</label>
                <select name="task_id" onchange="setEmployees()">{task_options}</select>
            </div>
            <div class="form-group" id="subtask_select" style="display:{'block' if pre_kind == 'subtask' else 'none'}">
                <label>Подзадача</label>
                <select name="task_id" onchange="setEmployees()">{subtask_options}</select>
            </div>
            <div class="form-group">
                <label>Сотрудник</label>
                <select name="employee_id" required onchange="setShareDefault()">{employee_options}</select>
            </div>
            <div class="form-group">
                <label>Доля (0.0 - 1.0)</label>
                <input type="number" name="share" step="0.1" min="0" max="1" value="1.0" required>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('task_assignments_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    <script>
    var taskProject = {task_proj_json};
    var projEmployees = {proj_emp_json};
    var empCount = {emp_count_json};
    function toggleTaskSelect(kind) {{
        document.getElementById('task_select').style.display = kind==='task' ? 'block' : 'none';
        document.getElementById('subtask_select').style.display = kind==='subtask' ? 'block' : 'none';
    }}
    function setEmployees() {{
        var empSel = document.querySelector('select[name=employee_id]');
        var cur = empSel.value;
        var kind = document.querySelector('select[name=task_kind]').value;
        var box = document.querySelector(kind==='task' ? '#task_select select' : '#subtask_select select');
        var taskId = box ? box.value : '';
        var pid = taskProject[kind + ':' + taskId];
        var opts = (pid && projEmployees[pid]) ? projEmployees[pid] : '<option value="">нет исполнителей, назначенных на проект</option>';
        empSel.innerHTML = opts;
        var has = Array.prototype.some.call(empSel.options, function(o) {{ return o.value === cur; }});
        if (cur) {{ empSel.value = has ? cur : ''; }}
        setShareDefault();
    }}
    function setShareDefault() {{
        var empSel = document.querySelector('select[name=employee_id]');
        var shareSel = document.querySelector('input[name=share]');
        var cnt = empCount[empSel.value] || 0;
        if (empSel.value) {{ shareSel.value = ((1 / (cnt + 1)) * 100 / 100).toFixed(2); }}
    }}
    setEmployees();
    </script>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новое назначение', content=content)

@app.route('/task_assignments/edit/<int:id>', methods=['GET', 'POST'])
def task_assignment_edit(id):
    db = get_db()
    if request.method == 'POST':
        task_id = int(request.form['task_id'])
        kind = request.form['task_kind']
        emp_id = int(request.form['employee_id'])
        if kind == 'task':
            pid = db.execute("SELECT COALESCE(ps.project_id, r.project_id) FROM task t LEFT JOIN project_stage ps ON t.stage_id=ps.id LEFT JOIN requirement r ON t.requirement_id=r.id WHERE t.id=? AND t.is_deleted=0", (task_id,)).fetchone()
        else:
            pid = db.execute("SELECT COALESCE(ps.project_id, r.project_id) FROM subtask s JOIN task t ON s.parent_task_id=t.id LEFT JOIN project_stage ps ON t.stage_id=ps.id LEFT JOIN requirement r ON t.requirement_id=r.id WHERE s.id=? AND s.is_deleted=0", (task_id,)).fetchone()
        if pid and pid[0] is not None:
            ok = db.execute("SELECT COUNT(*) FROM project_employee WHERE project_id=? AND employee_id=? AND is_deleted=0", (pid[0], emp_id)).fetchone()[0]
            if not ok:
                db.close()
                flash('Исполнитель не назначен на проект задачи', 'error')
                return redirect(url_for('task_assignments_list'))
        if kind == 'subtask':
            conflict = db.execute("SELECT id FROM task_assignment WHERE task_id=? AND task_kind='subtask' AND is_deleted=0 AND id<>?", (task_id, id)).fetchone()
            if conflict:
                db.close()
                flash('У подзадачи уже есть исполнитель (только один)', 'error')
                return redirect(url_for('task_assignments_list'))
        new_share = float(request.form['share'])
        cur_load = _projected_load_after(db, emp_id, kind, task_id, new_share, id)
        if cur_load > 1.0 + 1e-9:
            db.close()
            flash(f'Суммарная загрузка сотрудника не может превышать 100% ({round(cur_load * 100)}%)', 'error')
            return redirect(url_for('task_assignments_list'))
        db.execute("""UPDATE task_assignment SET task_id=?, task_kind=?, employee_id=?,
                     share=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (task_id,
                   kind,
                   emp_id,
                   new_share, id))
        db.commit()
        db.close()
        flash('Назначение обновлено', 'success')
        return redirect(url_for('task_assignments_list'))

    assignment = db.execute("SELECT * FROM task_assignment WHERE id=?", (id,)).fetchone()
    if not assignment:
        db.close()
        flash('Назначение не найдено', 'error')
        return redirect(url_for('task_assignments_list'))
    tasks = db.execute("SELECT id, description FROM task WHERE is_deleted=0").fetchall()
    subtasks = db.execute("SELECT id, description FROM subtask WHERE is_deleted=0").fetchall()
    employees = db.execute("SELECT id, last_name, first_name FROM employee WHERE is_deleted=0").fetchall()
    task_proj = {}
    for t in db.execute("""
        SELECT t.id, COALESCE(ps.project_id, r.project_id) pid FROM task t
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN requirement r ON t.requirement_id=r.id
        WHERE t.is_deleted=0
    """):
        task_proj['task:' + str(t['id'])] = t['pid']
    for s in db.execute("""
        SELECT s.id, COALESCE(ps.project_id, r.project_id) pid FROM subtask s
        JOIN task t ON s.parent_task_id=t.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN requirement r ON t.requirement_id=r.id
        WHERE s.is_deleted=0
    """):
        task_proj['subtask:' + str(s['id'])] = s['pid']
    proj_emp = _project_employee_options(db)
    db.close()

    task_options = ''.join([
                               f'<option value="{t["id"]}" {"selected" if t["id"] == assignment["task_id"] and assignment["task_kind"] == "task" else ""}>Задача: {t["description"][:50]}</option>'
                               for t in tasks])
    subtask_options = ''.join([
                                  f'<option value="{s["id"]}" {"selected" if s["id"] == assignment["task_id"] and assignment["task_kind"] == "subtask" else ""}>Подзадача: {s["description"][:50]}</option>'
                                  for s in subtasks])
    employee_options = ''.join([
                                   f'<option value="{e["id"]}" {"selected" if e["id"] == assignment["employee_id"] else ""}>{e["last_name"]} {e["first_name"]}</option>'
                                   for e in employees])
    task_proj_json = json.dumps({k: (str(v) if v else '') for k, v in task_proj.items()})
    proj_emp_json = json.dumps({str(k): ''.join(v) for k, v in proj_emp.items()})

    content = f'''
    <div class="card">
        <h2>Редактировать назначение</h2>
        <form method="POST">
            <div class="form-group">
                <label>Тип задачи</label>
                <select name="task_kind" required onchange="toggleTaskSelect(this.value); setEmployees()">
                    <option value="task" {"selected" if assignment["task_kind"] == "task" else ""}>Задача</option>
                    <option value="subtask" {"selected" if assignment["task_kind"] == "subtask" else ""}>Подзадача</option>
                </select>
            </div>
            <div class="form-group" id="task_select" style="display:{'block' if assignment['task_kind'] == 'task' else 'none'}">
                <label>Задача</label>
                <select name="task_id" onchange="setEmployees()">{task_options}</select>
            </div>
            <div class="form-group" id="subtask_select" style="display:{'block' if assignment['task_kind'] == 'subtask' else 'none'}">
                <label>Подзадача</label>
                <select name="task_id" onchange="setEmployees()">{subtask_options}</select>
            </div>
            <div class="form-group">
                <label>Сотрудник</label>
                <select name="employee_id" required>{employee_options}</select>
            </div>
            <div class="form-group">
                <label>Доля (0.0 - 1.0)</label>
                <input type="number" name="share" step="0.1" min="0" max="1" value="{assignment['share']}" required>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('task_assignments_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    <script>
    var taskProject = {task_proj_json};
    var projEmployees = {proj_emp_json};
    function toggleTaskSelect(kind) {{
        document.getElementById('task_select').style.display = kind==='task' ? 'block' : 'none';
        document.getElementById('subtask_select').style.display = kind==='subtask' ? 'block' : 'none';
    }}
    function setEmployees() {{
        var empSel = document.querySelector('select[name=employee_id]');
        var cur = empSel.value;
        var kind = document.querySelector('select[name=task_kind]').value;
        var box = document.querySelector(kind==='task' ? '#task_select select' : '#subtask_select select');
        var taskId = box ? box.value : '';
        var pid = taskProject[kind + ':' + taskId];
        var opts = (pid && projEmployees[pid]) ? projEmployees[pid] : '<option value="">нет исполнителей, назначенных на проект</option>';
        empSel.innerHTML = opts;
        var has = Array.prototype.some.call(empSel.options, function(o) {{ return o.value === cur; }});
        if (cur) {{ empSel.value = has ? cur : ''; }}
    }}
    setEmployees();
    </script>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать назначение', content=content)

@app.route('/task_assignments/delete/<int:id>')
def task_assignment_delete(id):
    db = get_db()
    db.execute("UPDATE task_assignment SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Назначение удалено', 'success')
    return redirect(url_for('task_assignments_list'))

