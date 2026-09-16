"""Проекты."""

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
    _project_requirements_html,
    _project_stage_tree_html,
    _project_stakeholders_html,
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

#==================== ПРОЕКТЫ ====================
@app.route('/projects')
def projects_list():
    db = get_db()
    projects = db.execute("""
        SELECT p.*, s.last_name, s.first_name, pr.name as priority_name, pr.weight
        FROM project p
        LEFT JOIN stakeholder s ON p.main_stakeholder_id = s.id
        JOIN priority pr ON p.priority_id = pr.id
        WHERE p.is_deleted=0
        ORDER BY p.id DESC
    """).fetchall()


    rows = ''.join([f'''
        <tr>
            <td>{p['id']}</td>
            <td><a href="{url_for('project_detail', id=p['id'])}">{p['name']}</a></td>
            <td>{f'<a href="{url_for("stakeholder_detail", id=p["main_stakeholder_id"])}">{p["last_name"]} {p["first_name"]}</a>' if p['main_stakeholder_id'] else '-'}</td>
            <td>{p['cost'] or '-'}</td>
            <td>{p['mvp_deadline'] or '-'}</td>
            <td>{p['deadline'] or '-'}</td>
            <td><span class="badge" style="background: {['#95a5a6','#3498db','#f39c12','#e67e22','#e74c3c'][p['weight']-1]}">{p['priority_name']}</span></td>
            <td>
                <a href="{url_for('project_detail', id=p['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('project_edit', id=p['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('project_delete', id=p['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for p in projects])

    content = f'''
    <div class="card">
        <h2>Проекты</h2>
        <a href="{url_for('project_create')}" class="btn btn-success">+ Добавить проект</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Название</th><th>Главный стейкхолдер</th><th>Стоимость</th><th>MVP срок</th><th>Проект срок</th><th>Приоритет</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Проекты', content=content)

@app.route('/projects/create', methods=['GET', 'POST'])
def project_create():
    db = get_db()
    if request.method == 'POST':
        db.execute("""INSERT INTO project (name, description, main_stakeholder_id, cost, mvp_deadline, deadline, priority_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (request.form['name'], request.form.get('description'),
                   request.form.get('main_stakeholder_id') or None,
                   request.form.get('cost') or None,
                   request.form.get('mvp_deadline') or None,
                   request.form.get('deadline') or None,
                   int(request.form['priority_id'])))
        db.commit()
        db.close()
        flash('Проект создан', 'success')
        return redirect(url_for('projects_list'))

    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    db.close()

    stakeholder_options = '<option value="">Не выбран</option>' + ''.join([f'<option value="{s["id"]}">{s["last_name"]} {s["first_name"]}</option>' for s in stakeholders])
    priority_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in priorities])

    content = f'''
    <div class="card">
        <h2>Новый проект</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description"></textarea>
            </div>
            <div class="form-group">
                <label>Главный стейкхолдер</label>
                <select name="main_stakeholder_id">{stakeholder_options}</select>
            </div>
            <div class="form-group">
                <label>Стоимость</label>
                <input type="number" name="cost" step="0.01">
            </div>
            <div class="form-group">
                <label>Срок MVP</label>
                <input type="date" name="mvp_deadline">
            </div>
            <div class="form-group">
                <label>Срок проекта</label>
                <input type="date" name="deadline">
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('projects_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый проект', content=content)

@app.route('/projects/edit/<int:id>', methods=['GET', 'POST'])
def project_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("""UPDATE project SET name=?, description=?, main_stakeholder_id=?, cost=?,
                     mvp_deadline=?, deadline=?, priority_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (request.form['name'], request.form.get('description'),
                   request.form.get('main_stakeholder_id') or None,
                   request.form.get('cost') or None,
                   request.form.get('mvp_deadline') or None,
                   request.form.get('deadline') or None,
                   int(request.form['priority_id']), id))
        db.commit()
        db.close()
        flash('Проект обновлён', 'success')
        return redirect(url_for('projects_list'))

    project = db.execute("SELECT * FROM project WHERE id=?", (id,)).fetchone()
    if not project:
        db.close()
        flash('Проект не найден', 'error')
        return redirect(url_for('projects_list'))
    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    db.close()

    stakeholder_options = '<option value="">Не выбран</option>' + ''.join([f'<option value="{s["id"]}" {"selected" if s["id"]==project["main_stakeholder_id"] else ""}>{s["last_name"]} {s["first_name"]}</option>' for s in stakeholders])
    priority_options = ''.join([f'<option value="{p["id"]}" {"selected" if p["id"]==project["priority_id"] else ""}>{p["name"]}</option>' for p in priorities])

    content = f'''
    <div class="card">
        <h2>Редактировать проект</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{project['name']}" required>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description">{project['description'] or ''}</textarea>
            </div>
            <div class="form-group">
                <label>Главный стейкхолдер</label>
                <select name="main_stakeholder_id">{stakeholder_options}</select>
            </div>
            <div class="form-group">
                <label>Стоимость</label>
                <input type="number" name="cost" value="{project['cost'] or ''}" step="0.01">
            </div>
            <div class="form-group">
                <label>Срок MVP</label>
                <input type="date" name="mvp_deadline" value="{project['mvp_deadline'] or ''}">
            </div>
            <div class="form-group">
                <label>Срок проекта</label>
                <input type="date" name="deadline" value="{project['deadline'] or ''}">
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('projects_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать проект', content=content)

@app.route('/projects/delete/<int:id>')
def project_delete(id):
    db = get_db()
    db.execute("UPDATE project SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Проект удалён', 'success')
    return redirect(url_for('projects_list'))

@app.route('/projects/<int:id>')
def project_detail(id):
    db = get_db()
    project = db.execute("""
        SELECT p.*, s.last_name, s.first_name, pr.name as priority_name, pr.weight
        FROM project p
        LEFT JOIN stakeholder s ON p.main_stakeholder_id = s.id
        JOIN priority pr ON p.priority_id = pr.id
        WHERE p.id=? AND p.is_deleted=0
    """, (id,)).fetchone()
    if not project:
        db.close()
        flash('Проект не найден', 'error')
        return redirect(url_for('projects_list'))

    req_block, req_count = _project_requirements_html(db, id)
    stages_block, stages_count = _project_stage_tree_html(db, id)
    stk_block, stk_count = _project_stakeholders_html(db, id)

    emp_rows = db.execute("""
        SELECT e.*, pe.project_id, pt.name position_name, es.name status_name, es.is_available
        FROM project_employee pe
        JOIN employee e ON pe.employee_id=e.id
        JOIN position_type pt ON e.position_type_id=pt.id
        JOIN employee_status es ON e.status_id=es.id
        WHERE pe.project_id=? AND pe.is_deleted=0 AND e.is_deleted=0
        ORDER BY e.last_name
    """, (id,)).fetchall()
    emp_ids = {e['id'] for e in emp_rows}
    def emp_remove_btn(eid):
        return f' <a href="{url_for("project_remove_employee", id=id, employee_id=eid)}" class="btn btn-danger" onclick="return confirm(\'Убрать?\')">Убрать</a>'
    emp_rows_html = ''.join([f'''
        <tr>
            <td class="name-cell"><a href="{url_for('employee_detail', id=e['id'])}">{e['last_name']} {e['first_name']} {e['middle_name'] or ''}</a></td>
            <td>{e['position_name']}</td>
            <td><span class="badge" style="background: {'#27ae60' if e['is_available'] else '#e74c3c'}">{e['status_name']}</span></td>
            <td>{e['subordinates_total']}</td>
            <td>
                <a href="{url_for('employee_detail', id=e['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('employee_edit', id=e['id'], origin=id)}" class="btn btn-primary">Изменить</a>{emp_remove_btn(e['id'])}
            </td>
        </tr>''' for e in emp_rows])
    emp_candidates = []
    if emp_ids:
        eph = ','.join('?' * len(emp_ids))
        emp_candidates = db.execute(f"""
            SELECT e.*, pt.name position_name FROM employee e JOIN position_type pt ON e.position_type_id=pt.id
            WHERE e.is_deleted=0 AND e.id NOT IN ({eph}) ORDER BY e.last_name
        """, tuple(list(emp_ids))).fetchall()
    else:
        emp_candidates = db.execute("SELECT e.*, pt.name position_name FROM employee e JOIN position_type pt ON e.position_type_id=pt.id WHERE e.is_deleted=0 ORDER BY e.last_name").fetchall()
    emp_candidate_options = ''.join(f'<option value="{e["id"]}">{e["last_name"]} {e["first_name"]} — {e["position_name"]}</option>' for e in emp_candidates)

    session['project_id'] = id
    active_tab = request.args.get('tab') or 'req'
    if active_tab not in ('req', 'stages', 'stk', 'emp'):
        active_tab = 'req'
    btn_d = {k: ('tab-btn active' if active_tab == k else 'tab-btn') for k in ('req', 'stages', 'stk', 'emp')}
    panel_d = {k: ('tab-content active' if active_tab == k else 'tab-content') for k in ('req', 'stages', 'stk', 'emp')}

    content = f'''
    <div class="card">
        <h2>{project['name']}
            <span class="node-meta">
                | Приоритет: {project['priority_name']}
                | Стейкхолдер: {f'<a href="{url_for("stakeholder_detail", id=project["main_stakeholder_id"])}">{project["last_name"]} {project["first_name"]}</a>' if project['main_stakeholder_id'] else '-'}
                | Стоимость: {project['cost'] or '-'}
                | Срок: {project['deadline'] or '-'}
            </span>
        </h2>
        <div class="tabs">
            <button class="{btn_d['req']}" id="btn-req" onclick="showTab('req')">Требования ({req_count})</button>
            <button class="{btn_d['stages']}" id="btn-stages" onclick="showTab('stages')">Этапы ({stages_count})</button>
            <button class="{btn_d['stk']}" id="btn-stk" onclick="showTab('stk')">Стейкхолдеры ({stk_count})</button>
            <button class="{btn_d['emp']}" id="btn-emp" onclick="showTab('emp')">Исполнители ({len(emp_rows)})</button>
        </div>
        <div class="{panel_d['req']}" id="tab-req">
            {req_block}
        </div>
        <div class="{panel_d['stages']}" id="tab-stages">
            {stages_block}
        </div>
        <div class="{panel_d['stk']}" id="tab-stk">
            {stk_block}
        </div>
        <div class="{panel_d['emp']}" id="tab-emp">
            <a href="{url_for('employee_create', project_id=id)}" class="btn btn-success">+ Добавить исполнителя</a>
            <form method="POST" action="{url_for('project_add_employee', id=id)}" style="display:inline-flex; gap:6px; margin-left:8px; vertical-align:middle;">
                <select name="employee_id" required>
                    <option value="">— выберите из имеющихся —</option>
                    {emp_candidate_options}
                </select>
                <button type="submit" class="btn btn-primary">Добавить</button>
            </form>
            <table>
                <thead>
                    <tr><th>Исполнитель</th><th>Должность</th><th>Статус</th><th>Подчинённые</th><th>Действия</th></tr>
                </thead>
                <tbody>{emp_rows_html}</tbody>
            </table>
        </div>
    </div>
    <script>
    function showTab(name) {{
        document.querySelectorAll('.tab-btn').forEach(function(el) {{ el.classList.remove('active'); }});
        document.querySelectorAll('.tab-content').forEach(function(el) {{ el.classList.remove('active'); }});
        document.getElementById('btn-' + name).classList.add('active');
        document.getElementById('tab-' + name).classList.add('active');
    }}
    </script>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title=project['name'], content=content)

@app.route('/projects/<int:id>/add_stakeholder', methods=['POST'])
def project_add_stakeholder(id):
    db = get_db()
    sid = int(request.form['stakeholder_id'])
    try:
        db.execute("INSERT INTO project_stakeholder (project_id, stakeholder_id) VALUES (?, ?)", (id, sid))
        db.commit()
        flash('Стейкхолдер добавлен к проекту', 'success')
    except sqlite3.IntegrityError:
        flash('Стейкхолдер уже в проекте', 'warning')
    db.close()
    return redirect(url_for('project_detail', id=id, tab='stk'))

@app.route('/projects/<int:id>/remove_stakeholder/<int:stakeholder_id>')
def project_remove_stakeholder(id, stakeholder_id):
    db = get_db()
    db.execute("UPDATE project_stakeholder SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE project_id=? AND stakeholder_id=?", (id, stakeholder_id))
    db.commit()
    db.close()
    flash('Стейкхолдер убран из проекта', 'success')
    return redirect(url_for('project_detail', id=id, tab='stk'))

@app.route('/projects/<int:id>/add_employee', methods=['POST'])
def project_add_employee(id):
    db = get_db()
    eid = int(request.form['employee_id'])
    try:
        db.execute("INSERT INTO project_employee (project_id, employee_id) VALUES (?, ?)", (id, eid))
        db.commit()
        flash('Исполнитель добавлен к проекту', 'success')
    except sqlite3.IntegrityError:
        flash('Исполнитель уже в проекте', 'warning')
    db.close()
    return redirect(url_for('project_detail', id=id, tab='emp'))

@app.route('/projects/<int:id>/remove_employee/<int:employee_id>')
def project_remove_employee(id, employee_id):
    db = get_db()
    db.execute("UPDATE project_employee SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE project_id=? AND employee_id=?", (id, employee_id))
    db.commit()
    db.close()
    flash('Исполнитель убран из проекта', 'success')
    return redirect(url_for('project_detail', id=id, tab='emp'))


