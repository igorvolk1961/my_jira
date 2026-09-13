"""Стейкхолдеры и интервью-связи."""

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

# ==================== СТЕЙКХОЛДЕРЫ ====================

@app.route('/stakeholders')
def stakeholders_list():
    db = get_db()
    stakeholders = db.execute("""
        SELECT s.*, st.name as type_name 
        FROM stakeholder s
        JOIN stakeholder_type st ON s.type_id = st.id
        WHERE s.is_deleted=0
        ORDER BY s.last_name
    """).fetchall()
    
    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td class="name-cell">{s['last_name']} {s['first_name']} {s['middle_name'] or ''}</td>
            <td>{s['type_name']}</td>
            <td>{s['position'] or '-'}</td>
            <td>{s['priority']}</td>
            <td>
                <a href="{url_for('stakeholder_detail', id=s['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('stakeholder_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('stakeholder_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in stakeholders])
    
    content = f'''
    <div class="card">
        <h2>Стейкхолдеры</h2>
        <a href="{url_for('stakeholder_create')}" class="btn btn-success">+ Добавить стейкхолдера</a>
        <table>
            <thead>
                <tr><th>ID</th><th>ФИО</th><th>Тип</th><th>Должность</th><th>Приоритет</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Стейкхолдеры', content=content)

@app.route('/stakeholders/create', methods=['GET', 'POST'])
def stakeholder_create():
    db = get_db()
    if request.method == 'POST':
        type_id = int(request.form['type_id'])
        dev_id = _developer_type_id(db)
        emp_id = (request.form.get('employee_id') or None) if type_id == dev_id else None
        cur = db.execute("""INSERT INTO stakeholder (last_name, first_name, middle_name, type_id, position, priority, employee_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (request.form['last_name'], request.form['first_name'],
                   request.form.get('middle_name'), type_id,
                   request.form.get('position'), int(request.form['priority']), emp_id))
        new_id = cur.lastrowid
        pid = request.form.get('project_id')
        if pid:
            db.execute("INSERT INTO project_stakeholder (project_id, stakeholder_id) VALUES (?, ?)", (int(pid), new_id))
        if emp_id:
            db.execute("UPDATE employee SET is_stackholder=1 WHERE id=? AND is_deleted=0", (int(emp_id),))
        db.commit()
        db.close()
        flash('Стейкхолдер создан', 'success')
        if pid:
            return redirect(url_for('project_detail', id=int(pid), tab='stk'))
        return redirect(url_for('stakeholders_list'))
    
    types = db.execute("SELECT * FROM stakeholder_type WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0 ORDER BY weight").fetchall()
    dev_id = _developer_type_id(db)
    linked_emp = {r[0] for r in db.execute("SELECT DISTINCT employee_id FROM stakeholder WHERE employee_id IS NOT NULL AND is_deleted=0")}
    employees = [e for e in db.execute("SELECT * FROM employee WHERE is_deleted=0 ORDER BY last_name") if e['id'] not in linked_emp]
    db.close()
    
    options = ''.join([f'<option value="{t["id"]}">{t["name"]}</option>' for t in types])
    priority_options = ''.join([
        f'<option value="{p["weight"]}" {"selected" if p["weight"] == 3 else ""}>{p["name"]}</option>'
        for p in priorities
    ])
    type_prio = ','.join(f'{t["id"]}:{int(t["influence_priority"])}' for t in types)
    employee_options = ''.join(f'<option value="{e["id"]}">{e["last_name"]} {e["first_name"]} {e["middle_name"] or ""}</option>' for e in employees)
    pre_project = request.args.get('project_id')
    cancel_url = url_for('project_detail', id=int(pre_project), tab='stk') if pre_project else url_for('stakeholders_list')
    
    content = f'''
    <div class="card">
        <h2>Новый стейкхолдер</h2>
        <form method="POST">
            <input type="hidden" name="project_id" value="{pre_project or ''}">
            <div class="form-group">
                <label>Фамилия</label>
                <input type="text" name="last_name" required>
            </div>
            <div class="form-group">
                <label>Имя</label>
                <input type="text" name="first_name" required>
            </div>
            <div class="form-group">
                <label>Отчество</label>
                <input type="text" name="middle_name">
            </div>
            <div class="form-group">
                <label>Тип стейкхолдера</label>
                <select name="type_id" required onchange="setPrio(this.value); toggleEmp()">{options}</select>
            </div>
            <div class="form-group" id="employee_select" style="display:none;">
                <label>Сотрудник</label>
                <select name="employee_id"><option value="">— не выбран —</option>{employee_options}</select>
            </div>
            <div class="form-group">
                <label>Должность</label>
                <input type="text" name="position">
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority" required>{priority_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    <script>
    var prioByType = {{ {type_prio} }};
    var devType = {dev_id};
    function setPrio(tid) {{
        var p = prioByType[tid];
        if (p) {{ document.querySelector('select[name=priority]').value = p; }}
    }}
    function toggleEmp() {{
        var v = document.querySelector('select[name=type_id]').value;
        document.getElementById('employee_select').style.display = (v == devType) ? 'block' : 'none';
    }}
    toggleEmp();
    </script>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый стейкхолдер', content=content)

@app.route('/stakeholders/edit/<int:id>', methods=['GET', 'POST'])
def stakeholder_edit(id):
    db = get_db()
    if request.method == 'POST':
        type_id = int(request.form['type_id'])
        dev_id = _developer_type_id(db)
        emp_id = (request.form.get('employee_id') or None) if type_id == dev_id else None
        old = db.execute("SELECT employee_id FROM stakeholder WHERE id=?", (id,)).fetchone()
        db.execute("""UPDATE stakeholder SET last_name=?, first_name=?, middle_name=?, type_id=?,
                     position=?, priority=?, employee_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (request.form['last_name'], request.form['first_name'],
                   request.form.get('middle_name'), type_id,
                   request.form.get('position'), int(request.form['priority']), emp_id, id))
        if emp_id:
            db.execute("UPDATE employee SET is_stackholder=1 WHERE id=? AND is_deleted=0", (int(emp_id),))
        old_eid = old[0] if old else None
        if old_eid and str(old_eid) != (emp_id or ''):
            _reset_employee_stackholder_if_unlinked(db, old_eid)
        db.commit()
        db.close()
        flash('Стейкхолдер обновлён', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='stk'))
        return redirect(url_for('stakeholders_list'))
    
    stakeholder = db.execute("SELECT * FROM stakeholder WHERE id=?", (id,)).fetchone()
    if not stakeholder:
        db.close()
        flash('Стейкхолдер не найден', 'error')
        return redirect(url_for('stakeholders_list'))
    types = db.execute("SELECT * FROM stakeholder_type WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0 ORDER BY weight").fetchall()
    dev_id = _developer_type_id(db)
    linked_emp = {r[0] for r in db.execute("SELECT DISTINCT employee_id FROM stakeholder WHERE employee_id IS NOT NULL AND is_deleted=0")}
    employees = [e for e in db.execute("SELECT * FROM employee WHERE is_deleted=0 ORDER BY last_name") if e['id'] not in linked_emp]
    if stakeholder['employee_id'] and all(e['id'] != stakeholder['employee_id'] for e in employees):
        cur_e = db.execute("SELECT * FROM employee WHERE id=? AND is_deleted=0", (stakeholder['employee_id'],)).fetchone()
        if cur_e:
            employees.append(cur_e)
    db.close()
    
    options = ''.join([f'<option value="{t["id"]}" {"selected" if t["id"]==stakeholder["type_id"] else ""}>{t["name"]}</option>' for t in types])
    priority_options = ''.join([
        f'<option value="{p["weight"]}" {"selected" if p["weight"]==stakeholder["priority"] else ""}>{p["name"]}</option>'
        for p in priorities
    ])
    type_prio = ','.join(f'{t["id"]}:{int(t["influence_priority"])}' for t in types)
    employee_options = ''.join(
        f'<option value="{e["id"]}" {"selected" if e["id"] == stakeholder["employee_id"] else ""}>{e["last_name"]} {e["first_name"]} {e["middle_name"] or ""}</option>'
        for e in employees)
    origin = request.args.get('origin')
    cancel_url = url_for('project_detail', id=int(origin), tab='stk') if origin else url_for('stakeholders_list')
    
    content = f'''
    <div class="card">
        <h2>Редактировать стейкхолдера</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Фамилия</label>
                <input type="text" name="last_name" value="{stakeholder['last_name']}" required>
            </div>
            <div class="form-group">
                <label>Имя</label>
                <input type="text" name="first_name" value="{stakeholder['first_name']}" required>
            </div>
            <div class="form-group">
                <label>Отчество</label>
                <input type="text" name="middle_name" value="{stakeholder['middle_name'] or ''}">
            </div>
            <div class="form-group">
                <label>Тип стейкхолдера</label>
                <select name="type_id" required onchange="setPrio(this.value); toggleEmp()">{options}</select>
            </div>
            <div class="form-group" id="employee_select" style="display:{'block' if stakeholder['type_id'] == dev_id else 'none'};">
                <label>Сотрудник</label>
                <select name="employee_id"><option value="">— не выбран —</option>{employee_options}</select>
            </div>
            <div class="form-group">
                <label>Должность</label>
                <input type="text" name="position" value="{stakeholder['position'] or ''}">
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority" required>{priority_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    <script>
    var prioByType = {{ {type_prio} }};
    var devType = {dev_id};
    function setPrio(tid) {{
        var p = prioByType[tid];
        if (p) {{ document.querySelector('select[name=priority]').value = p; }}
    }}
    function toggleEmp() {{
        var v = document.querySelector('select[name=type_id]').value;
        document.getElementById('employee_select').style.display = (v == devType) ? 'block' : 'none';
    }}
    toggleEmp();
    </script>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать стейкхолдера', content=content)

@app.route('/stakeholders/delete/<int:id>')
def stakeholder_delete(id):
    db = get_db()
    st = db.execute("SELECT employee_id FROM stakeholder WHERE id=? AND is_deleted=0", (id,)).fetchone()
    db.execute("UPDATE stakeholder SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    if st and st['employee_id']:
        _reset_employee_stackholder_if_unlinked(db, st['employee_id'])
    db.commit()
    db.close()
    flash('Стейкхолдер удалён', 'success')
    return redirect(url_for('stakeholders_list'))


