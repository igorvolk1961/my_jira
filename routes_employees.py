"""Сотрудники."""

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
from app_core import (  # noqa: F401
    current_user,
    is_admin,
    is_analyst,
    role_label,
    sync_analyst_role_from_position,
    sync_position_from_analyst_role,
)

#==================== СОТРУДНИКИ ====================
@app.route('/employees')
def employees_list():
    db = get_db()
    employees = db.execute("""
        SELECT e.*, pt.name as position_name, es.name as status_name, es.is_available,
               u.id AS user_id, u.role AS user_role, u.is_analyst AS user_analyst
        FROM employee e
        JOIN position_type pt ON e.position_type_id = pt.id
        JOIN employee_status es ON e.status_id = es.id
        LEFT JOIN app_user u ON u.employee_id = e.id AND u.is_deleted = 0
        WHERE e.is_deleted=0
        ORDER BY e.last_name
    """).fetchall()
    _me = current_user()
    self_emp_id = _me['employee_id'] if _me else None
    admin = is_admin()
    role_labels = {'admin': 'администратор', 'user': 'пользователь'}

    rows = ''
    for e in employees:
        delete_btn = ''
        if e['id'] != self_emp_id:
            delete_btn = (f'<a href="{url_for("employee_delete", id=e["id"])}" class="btn btn-danger" '
                          f'onclick="return confirm(\'Удалить?\')">Удалить</a>')
        if not e['user_id']:
            role_cell = '<span class="muted">—</span>'
        elif admin and e['id'] != self_emp_id:
            opts = ''.join([
                f'<option value="{r}" {"selected" if r == e["user_role"] else ""}>{label}</option>'
                for r, label in role_labels.items()])
            checked = 'checked' if e['user_analyst'] else ''
            role_cell = (f'<form method="POST" action="{url_for("employee_role_change", id=e["id"])}" '
                         f'style="display:inline-flex; gap:4px; align-items:center; margin:0; flex-wrap:wrap;">'
                         f'<select name="role">{opts}</select>'
                         f'<label style="white-space:nowrap;"><input type="checkbox" name="is_analyst" value="1" {checked} '
                         f'style="width:auto; display:inline; margin-right:4px;">сист. аналитик</label>'
                         f'<button type="submit" class="btn btn-primary" style="margin:0;">OK</button></form>')
        else:
            role_cell = role_label(e['user_role'], e['user_analyst'])
        rows += f'''
        <tr>
            <td>{e['id']}</td>
            <td class="name-cell">{e['last_name']} {e['first_name']} {e['middle_name'] or ''}</td>
            <td>{e['position_name']}</td>
            <td><span class="badge" style="background: {'#27ae60' if e['is_available'] else '#e74c3c'}">{e['status_name']}</span></td>
            <td>{role_cell}</td>
            <td>{e['subordinates_total']}</td>
            <td>{e['subordinates_available']}</td>
            <td>
                <a href="{url_for('employee_detail', id=e['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('employee_edit', id=e['id'])}" class="btn btn-primary">Изменить</a>
                {delete_btn}
            </td>
        </tr>'''

    content = f'''
    <div class="card">
        <h2>Сотрудники</h2>
        <a href="{url_for('employee_create')}" class="btn btn-success">+ Добавить сотрудника</a>
        <table>
            <thead>
                <tr><th>ID</th><th>ФИО</th><th>Должность</th><th>Статус</th><th>Роль</th><th>Всего подчинённых</th><th>Доступно подчинённых</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Сотрудники', content=content)

@app.route('/employees/create', methods=['GET', 'POST'])
def employee_create():
    db = get_db()
    if request.method == 'POST':
        is_sh = 1 if request.form.get('is_stackholder') else 0
        cur = db.execute("""INSERT INTO employee (last_name, first_name, middle_name, position_type_id, status_id, subordinates_total, subordinates_available, is_stackholder)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (request.form['last_name'], request.form['first_name'],
                   request.form.get('middle_name'),
                   int(request.form['position_type_id']),
                   int(request.form['status_id']),
                   int(request.form.get('subordinates_total', 0)),
                   int(request.form.get('subordinates_available', 0)),
                   is_sh))
        new_id = cur.lastrowid
        pid = request.form.get('project_id')
        if pid:
            db.execute("INSERT INTO project_employee (project_id, employee_id) VALUES (?, ?)", (int(pid), new_id))
        sync_stakeholder_for_employee(db, new_id, bool(is_sh))
        sync_analyst_role_from_position(db, new_id)
        db.commit()
        db.close()
        flash('Сотрудник создан', 'success')
        if pid:
            return redirect(url_for('project_detail', id=int(pid), tab='emp'))
        return redirect(url_for('employees_list'))

    positions = db.execute("SELECT * FROM position_type WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM employee_status WHERE is_deleted=0").fetchall()
    db.close()

    position_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in positions])
    status_options = ''.join([f'<option value="{s["id"]}">{s["name"]}</option>' for s in statuses])
    pre_project = request.args.get('project_id')
    cancel_url = url_for('project_detail', id=int(pre_project), tab='emp') if pre_project else url_for('employees_list')

    content = f'''
    <div class="card">
        <h2>Новый сотрудник</h2>
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
                <label>Тип должности</label>
                <select name="position_type_id" required>{position_options}</select>
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <div class="form-group">
                <label>Всего подчинённых</label>
                <input type="number" name="subordinates_total" value="0" min="0">
            </div>
            <div class="form-group">
                <label>Доступно подчинённых</label>
                <input type="number" name="subordinates_available" value="0" min="0">
            </div>
            <div class="form-group">
                <label><input type="checkbox" name="is_stackholder" value="1" style="width:auto; display:inline; margin-right:6px;"> Является стейкхолдером (разработчик)</label>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый сотрудник', content=content)

@app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
def employee_edit(id):
    db = get_db()
    if request.method == 'POST':
        is_sh = 1 if request.form.get('is_stackholder') else 0
        db.execute("""UPDATE employee SET last_name=?, first_name=?, middle_name=?, position_type_id=?,
                     status_id=?, subordinates_total=?, subordinates_available=?, is_stackholder=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (request.form['last_name'], request.form['first_name'],
                   request.form.get('middle_name'),
                   int(request.form['position_type_id']),
                   int(request.form['status_id']),
                   int(request.form.get('subordinates_total', 0)),
                   int(request.form.get('subordinates_available', 0)), is_sh, id))
        sync_stakeholder_for_employee(db, id, bool(is_sh))
        sync_analyst_role_from_position(db, id)
        db.commit()
        db.close()
        flash('Сотрудник обновлён', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='emp'))
        return redirect(url_for('employees_list'))

    employee = db.execute("SELECT * FROM employee WHERE id=?", (id,)).fetchone()
    if not employee:
        db.close()
        flash('Сотрудник не найден', 'error')
        return redirect(url_for('employees_list'))
    positions = db.execute("SELECT * FROM position_type WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM employee_status WHERE is_deleted=0").fetchall()
    db.close()

    position_options = ''.join([
                                   f'<option value="{p["id"]}" {"selected" if p["id"] == employee["position_type_id"] else ""}>{p["name"]}</option>'
                                   for p in positions])
    status_options = ''.join(
        [f'<option value="{s["id"]}" {"selected" if s["id"] == employee["status_id"] else ""}>{s["name"]}</option>' for
         s in statuses])
    origin = request.args.get('origin')
    cancel_url = url_for('project_detail', id=int(origin), tab='emp') if origin else url_for('employees_list')

    content = f'''
    <div class="card">
        <h2>Редактировать сотрудника</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Фамилия</label>
                <input type="text" name="last_name" value="{employee['last_name']}" required>
            </div>
            <div class="form-group">
                <label>Имя</label>
                <input type="text" name="first_name" value="{employee['first_name']}" required>
            </div>
            <div class="form-group">
                <label>Отчество</label>
                <input type="text" name="middle_name" value="{employee['middle_name'] or ''}">
            </div>
            <div class="form-group">
                <label>Тип должности</label>
                <select name="position_type_id" required>{position_options}</select>
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <div class="form-group">
                <label>Всего подчинённых</label>
                <input type="number" name="subordinates_total" value="{employee['subordinates_total']}" min="0">
            </div>
            <div class="form-group">
                <label>Доступно подчинённых</label>
                <input type="number" name="subordinates_available" value="{employee['subordinates_available']}" min="0">
            </div>
            <div class="form-group">
                <label><input type="checkbox" name="is_stackholder" value="1" style="width:auto; display:inline; margin-right:6px;" {'checked' if employee['is_stackholder'] else ''}> Является стейкхолдером (разработчик)</label>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать сотрудника', content=content)

@app.route('/employees/delete/<int:id>')
def employee_delete(id):
    db = get_db()
    me = current_user()
    if me and me['employee_id'] == id:
        db.close()
        flash('Нельзя удалить собственную учётную запись', 'error')
        return redirect(url_for('employees_list'))
    # Удаляем учётные записи пользователей, связанных с этим сотрудником,
    # чтобы не оставлять «висячие» app_user.employee_id.
    linked = db.execute("SELECT COUNT(*) FROM app_user WHERE employee_id=? AND is_deleted=0", (id,)).fetchone()[0]
    db.execute("UPDATE app_user SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE employee_id=? AND is_deleted=0", (id,))
    db.execute("UPDATE employee SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Сотрудник и связанный пользователь удалены' if linked else 'Сотрудник удалён', 'success')
    return redirect(url_for('employees_list'))


@app.route('/employees/role/<int:id>', methods=['POST'])
def employee_role_change(id):
    db = get_db()
    me = current_user()
    role = request.form.get('role')
    want_analyst = 1 if request.form.get('is_analyst') else 0
    if role not in ('admin', 'user'):
        db.close()
        flash('Некорректная роль', 'error')
        return redirect(url_for('employees_list'))
    user = db.execute("SELECT id FROM app_user WHERE employee_id=? AND is_deleted=0", (id,)).fetchone()
    if not user:
        db.close()
        flash('У сотрудника нет учётной записи пользователя', 'error')
        return redirect(url_for('employees_list'))
    if me and me['employee_id'] == id:
        db.close()
        flash('Нельзя изменить собственную роль', 'error')
        return redirect(url_for('employees_list'))
    db.execute("UPDATE app_user SET role=?, is_analyst=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (role, want_analyst, user['id']))
    sync_position_from_analyst_role(db, id, bool(want_analyst))
    db.commit()
    db.close()
    flash('Роли пользователя обновлены', 'success')
    return redirect(url_for('employees_list'))


