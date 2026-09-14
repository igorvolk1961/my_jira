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

    requirements = db.execute("""
        SELECT r.*, s.last_name, s.first_name, rt.name as type_name, pr.name as priority_name
        FROM requirement r
        LEFT JOIN stakeholder s ON r.stakeholder_id = s.id
        JOIN requirement_type rt ON r.requirement_type_id = rt.id
        JOIN priority pr ON r.priority_id = pr.id
        WHERE r.project_id=? AND r.is_deleted=0
        ORDER BY r.id DESC
    """, (id,)).fetchall()

    stages = db.execute("""
        SELECT ps.*, pst.name as type_name, pss.name as status_name, pss.color
        FROM project_stage ps
        JOIN project_stage_type pst ON ps.stage_type_id = pst.id
        JOIN project_stage_status pss ON ps.status_id = pss.id
        WHERE ps.project_id=? AND ps.is_deleted=0
        ORDER BY pst.sort_order
    """, (id,)).fetchall()

    tasks = db.execute("""
        SELECT t.*, ps.id as stage_id, pr.name as priority_name,
               ts.name as status_name, ts.color as status_color, tt.name as type_name
        FROM task t
        JOIN priority pr ON t.priority_id = pr.id
        JOIN task_status ts ON t.status_id = ts.id
        LEFT JOIN project_stage ps ON t.stage_id = ps.id
        LEFT JOIN requirement r ON t.requirement_id = r.id
        LEFT JOIN task_type tt ON t.task_type_id = tt.id
        WHERE t.is_deleted=0 AND (ps.project_id=? OR r.project_id=?)
        ORDER BY t.id
    """, (id, id)).fetchall()

    task_ids = [t['id'] for t in tasks]
    subtasks = []
    if task_ids:
        ph = ','.join('?' * len(task_ids))
        subtasks = db.execute(f"""
            SELECT st.*, pr.name as priority_name, ts.name as status_name, ts.color as status_color
            FROM subtask st
            JOIN priority pr ON st.priority_id = pr.id
            JOIN task_status ts ON st.status_id = ts.id
            WHERE st.is_deleted=0 AND st.parent_task_id IN ({ph})
            ORDER BY st.id
        """, tuple(task_ids)).fetchall()
    sub_children = {}
    top_by_task = {}
    for st in subtasks:
        sub_children.setdefault(st['parent_subtask_id'], []).append(st)
        if st['parent_subtask_id'] is None:
            top_by_task.setdefault(st['parent_task_id'], []).append(st)

    assignments = {}
    def collect_assignments(kind, ids):
        if not ids:
            return
        ph = ','.join('?' * len(ids))
        rows = db.execute(f"""
            SELECT ta.*, e.id as eid, e.last_name, e.first_name,
                   COALESCE(TRIM(au.last_name || ' ' || au.first_name), ap.login, '—') as assigner
            FROM task_assignment ta JOIN employee e ON ta.employee_id = e.id
            LEFT JOIN app_user ap ON ta.assigned_by_user_id = ap.id
            LEFT JOIN employee au ON ap.employee_id = au.id
            WHERE ta.is_deleted=0 AND ta.task_kind=? AND ta.task_id IN ({ph})
        """, tuple([kind] + list(ids))).fetchall()
        for a in rows:
            assignments.setdefault((kind, a['task_id']), []).append(a)
    collect_assignments('task', task_ids)
    collect_assignments('subtask', [s['id'] for s in subtasks])

    # Сотрудник, занятый в подзадаче, не показывается как исполнитель родительской задачи/подзадачи
    covered_by_emp = {}
    for (k, eidkey), rows in assignments.items():
        for a in rows:
            emp = a['employee_id']
            if emp not in covered_by_emp:
                covered_by_emp[emp] = _covered_for_employee(db, emp)
    def _not_covered(k, tid, emp):
        return (k, tid) not in covered_by_emp.get(emp, set())
    assignments = {(k, tid): [a for a in rows if _not_covered(k, tid, a['employee_id'])]
                   for (k, tid), rows in assignments.items()}

    def render_assignees(lines):
        if not lines:
            return '<span class="muted">исполнители не назначены</span>'
        items = [f'<a href="{url_for("employee_detail", id=a["eid"])}">{html.escape(a["last_name"])} {html.escape(a["first_name"])}</a> ({int(a["share"] * 100)}%, назначил: {html.escape(a["assigner"] or "—")})' for a in lines]
        return 'Исполнители: ' + ', '.join(items)

    def render_assignments_block(kind, tid):
        return f'<div class="assign">{render_assignees(assignments.get((kind, tid), []))}</div>'

    def render_subtask(st):
        children = sub_children.get(st['id'], [])
        asg = url_for('task_assignment_create', task_id=st['id'], task_kind='subtask', origin=id)
        edit_link = url_for('subtask_edit', id=st['id'], origin=id)
        card_link = url_for('subtask_detail', id=st['id'])
        child_link = url_for('subtask_create', parent_subtask_id=st['id'], origin=id)
        del_link = url_for('subtask_delete', id=st['id'])
        overdue = bool(st['deadline']) and str(st['deadline']) < date.today().isoformat() and st['status_name'] not in ('Выполнена', 'Отменена')
        deadline_style = ' color:#e74c3c; font-weight:bold;' if overdue else ''
        return f'''
            <details class="subtask" open>
                <summary>
                    <span class="node-info">
                        <a href="{card_link}">Подзадача #{st['id']}</a>
                        <span class="badge" style="background: {st['status_color'] or '#95a5a6'}">{st['status_name']}</span>
                        <span class="node-meta">Приоритет: {st['priority_name']}</span>
                        <span class="node-meta" style="{deadline_style}">Срок: {st['deadline'] or '-'}</span>
                    </span>
                    <span class="node-actions">
                        <a class="btn btn-warning" href="{asg}">Назначить</a>
                        <a class="btn btn-primary" href="{edit_link}">Изменить</a>
                        <a class="btn btn-success" href="{child_link}">+ Подзадача</a>
                        <a class="btn btn-danger" href="{del_link}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">
                    {render_assignments_block('subtask', st['id'])}
                    {''.join([render_subtask(c) for c in children])}
                </div>
            </details>'''

    def render_task(t):
        task_subtasks = top_by_task.get(t['id'], [])
        subtask_html = ''.join([render_subtask(s) for s in task_subtasks])
        asg = url_for('task_assignment_create', task_id=t['id'], task_kind='task', origin=id)
        subtask_link = url_for('subtask_create', parent_task_id=t['id'], origin=id)
        edit_link = url_for('task_edit', id=t['id'], origin=id)
        card_link = url_for('task_detail', id=t['id'])
        del_link = url_for('task_delete', id=t['id'])
        overdue = bool(t['deadline']) and str(t['deadline']) < date.today().isoformat() and t['status_name'] not in ('Выполнена', 'Отменена')
        deadline_style = ' color:#e74c3c; font-weight:bold;' if overdue else ''
        return f'''
            <details class="task" open>
                <summary>
                    <span class="node-info">
                        <a href="{card_link}">Задача #{t['id']}</a>
                        <span class="badge" style="background: {t['status_color'] or '#95a5a6'}">{t['status_name']}</span>
                        <span class="node-meta">Тип: {t['type_name'] or '-'}</span>
                        <span class="node-meta">Приоритет: {t['priority_name']}</span>
                        <span class="node-meta" style="{deadline_style}">Срок: {t['deadline'] or '-'}</span>
                    </span>
                    <span class="node-actions">
                        <a class="btn btn-warning" href="{asg}">Назначить</a>
                        <a class="btn btn-primary" href="{edit_link}">Изменить</a>
                        <a class="btn btn-success" href="{subtask_link}">+ Подзадача</a>
                        <a class="btn btn-danger" href="{del_link}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">
                    {render_assignments_block('task', t['id'])}
                    {subtask_html}
                </div>
            </details>'''

    tasks_by_stage = {}
    no_stage = []
    for t in tasks:
        if t['stage_id'] is None:
            no_stage.append(t)
        else:
            tasks_by_stage.setdefault(t['stage_id'], []).append(t)

    stage_html = ''
    for s in stages:
        stage_tasks = tasks_by_stage.get(s['id'], [])
        inner = ''.join([render_task(t) for t in stage_tasks])
        if not stage_tasks:
            inner = '<div class="node-body muted">Задач по этапу нет</div>'
        stage_html += f'''
            <details class="stage" open>
                <summary>
                    <span class="node-info">
                        {s['type_name']}
                        <span class="badge" style="background: {s['color'] or '#95a5a6'}">{s['status_name']}</span>
                        <span class="node-meta">План. окончание: {s['planned_end'] or '-'}</span>
                    </span>
                    <span class="node-actions">
                        <a class="btn btn-success" href="{url_for('task_create', stage_id=s['id'], origin=id)}">+ Задача</a>
                        <a class="btn btn-danger" href="{url_for('project_stage_delete', id=s['id'])}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">{inner}</div>
            </details>'''
    req_rows = ''.join([f'''
        <tr>
            <td>{r['id']}</td>
            <td>{r['type_name']}</td>
            <td>{r['last_name'] or '-'} {r['first_name'] or ''}</td>
            <td>{r['description'][:80]}</td>
            <td>{r['priority_name']}</td>
            <td>
                <a href="{url_for('requirement_detail', id=r['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('requirement_edit', id=r['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('requirement_delete', id=r['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>''' for r in requirements])

    main_id = project['main_stakeholder_id']
    assoc_rows = db.execute("SELECT stakeholder_id FROM project_stakeholder WHERE project_id=? AND is_deleted=0", (id,)).fetchall()
    assoc_ids = {a['stakeholder_id'] for a in assoc_rows}
    req_st_ids = {row[0] for row in db.execute("SELECT DISTINCT stakeholder_id FROM requirement WHERE project_id=? AND stakeholder_id IS NOT NULL AND is_deleted=0", (id,))}
    stk_ids = set(assoc_ids)
    if main_id:
        stk_ids.add(main_id)
    stk_ids |= req_st_ids
    project_stakeholders = []
    if stk_ids:
        ph = ','.join('?' * len(stk_ids))
        project_stakeholders = db.execute(f"""
            SELECT s.*, st.name type_name, st.influence_priority inf, st.interest_priority ints,
                   (SELECT COUNT(*) FROM requirement r WHERE r.stakeholder_id=s.id AND r.project_id=? AND r.is_deleted=0) req_count
            FROM stakeholder s JOIN stakeholder_type st ON s.type_id=st.id
            WHERE s.is_deleted=0 AND s.id IN ({ph})
            ORDER BY s.last_name
        """, tuple([id] + list(stk_ids))).fetchall()
    def stk_quadrant(inf, ints):
        if inf >= 4 and ints >= 4:
            return 'Ключевые игроки'
        if inf >= 4:
            return 'Удовлетворять'
        if ints >= 4:
            return 'Держать в курсе'
        return 'Наблюдать'
    def remove_btn(sid):
        if sid in assoc_ids and sid != main_id:
            return f' <a href="{url_for("project_remove_stakeholder", id=id, stakeholder_id=sid)}" class="btn btn-danger" onclick="return confirm(\'Убрать?\')">Убрать</a>'
        return ''
    stk_rows = ''.join([f'''
        <tr>
            <td class="name-cell"><a href="{url_for('stakeholder_detail', id=s['id'])}">{s['last_name']} {s['first_name']}</a> {f'<span class="badge" style="background:#e74c3c">главный</span>' if s['id'] == main_id else ''}{f' <span class="badge" style="background:#3498db">добавлен</span>' if s['id'] in assoc_ids and s['id'] != main_id else ''}</td>
            <td>{s['type_name']}</td>
            <td>{s['inf']}/5, {s['ints']}/5</td>
            <td>{stk_quadrant(s['inf'], s['ints'])}</td>
            <td>{s['position'] or '-'}</td>
            <td>{s['req_count']}</td>
            <td><a href="{url_for('stakeholder_detail', id=s['id'])}" class="btn btn-success">Открыть</a> <a href="{url_for('stakeholder_edit', id=s['id'], origin=id)}" class="btn btn-primary">Изменить</a>{remove_btn(s['id'])}</td>
        </tr>''' for s in project_stakeholders])
    candidate_rows = []
    if stk_ids:
        cph = ','.join('?' * len(stk_ids))
        candidate_rows = db.execute(f"""
            SELECT s.*, st.name type_name FROM stakeholder s JOIN stakeholder_type st ON s.type_id=st.id
            WHERE s.is_deleted=0 AND s.id NOT IN ({cph})
            ORDER BY s.last_name
        """, tuple(list(stk_ids))).fetchall()
    else:
        candidate_rows = db.execute("SELECT s.*, st.name type_name FROM stakeholder s JOIN stakeholder_type st ON s.type_id=st.id WHERE s.is_deleted=0 ORDER BY s.last_name").fetchall()
    candidate_options = ''.join(f'<option value="{s["id"]}">{s["last_name"]} {s["first_name"]} — {s["type_name"]}</option>' for s in candidate_rows)

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
            <button class="{btn_d['req']}" id="btn-req" onclick="showTab('req')">Требования ({len(requirements)})</button>
            <button class="{btn_d['stages']}" id="btn-stages" onclick="showTab('stages')">Этапы ({len(stages)})</button>
            <button class="{btn_d['stk']}" id="btn-stk" onclick="showTab('stk')">Стейкхолдеры ({len(project_stakeholders)})</button>
            <button class="{btn_d['emp']}" id="btn-emp" onclick="showTab('emp')">Исполнители ({len(emp_rows)})</button>
        </div>
        <div class="{panel_d['req']}" id="tab-req">
            <a href="{url_for('requirement_create', project_id=id)}" class="btn btn-success">+ Добавить требование</a>
            <table>
                <thead>
                    <tr><th>ID</th><th>Тип</th><th>Стейкхолдер</th><th>Описание</th><th>Приоритет</th><th>Действия</th></tr>
                </thead>
                <tbody>{req_rows}</tbody>
            </table>
        </div>
        <div class="{panel_d['stages']}" id="tab-stages">
            <a href="{url_for('project_stage_create')}" class="btn btn-success">+ Добавить этап</a>
            <div class="tree">{stage_html}</div>
        </div>
        <div class="{panel_d['stk']}" id="tab-stk">
            <a href="{url_for('stakeholder_create', project_id=id)}" class="btn btn-success">+ Добавить стейкхолдера</a>
            <form method="POST" action="{url_for('project_add_stakeholder', id=id)}" style="display:inline-flex; gap:6px; margin-left:8px; vertical-align:middle;">
                <select name="stakeholder_id" required>
                    <option value="">— выберите из имеющихся —</option>
                    {candidate_options}
                </select>
                <button type="submit" class="btn btn-primary">Добавить</button>
            </form>
            <table>
                <thead>
                    <tr><th>Стейкхолдер</th><th>Тип</th><th>Влияние/Интерес</th><th>Квадрант</th><th>Должность</th><th>Требований</th><th>Действия</th></tr>
                </thead>
                <tbody>{stk_rows}</tbody>
            </table>
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


